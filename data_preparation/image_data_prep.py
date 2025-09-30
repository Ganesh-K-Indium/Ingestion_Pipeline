import io
import os
import fitz
import json
import openai
import base64
import hashlib
from datetime import datetime
from PIL import Image, ImageEnhance
from langchain.schema import Document
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()



class ImageDescription:
    "This method is used to get the description of the image."
    def __init__(self,pdf_path):
        """
        This constructor is used to initialize the path of the pdf.
        Args:
            pdf_path : The path of the pdf.
        """
        self.pdf_path = pdf_path
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if not self.openai_client.api_key:
            raise ValueError("OpenAI API key not found in environment variables")
    
    def get_pdf_data(self):
        """
        this method is used to get the fitz object (pdf_document) of the pdf.
        Args:
            None
        Return:
            pdf_document : fitz object of the pdf document.
        """
        pdf_document = fitz.open(self.pdf_path)
        return pdf_document
    
    def save_images(self,img_info,page_num,pdf_document,output_dir):
        """
        Advanced image preprocessing for optimal financial data extraction.
        """
        try:
            xref = img_info[0]
            base_image = pdf_document.extract_image(xref)
            if not base_image:
                return None, None
                
            image_bytes = base_image["image"]
            original_img = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB for consistent processing
            if original_img.mode != 'RGB':
                img = original_img.convert('RGB')
            else:
                img = original_img.copy()
            
            # Multi-stage image enhancement for financial documents
            
            # 1. Contrast enhancement for better text/number visibility
            contrast_enhancer = ImageEnhance.Contrast(img)
            img = contrast_enhancer.enhance(1.3)  # Slightly higher for financial docs
            
            # 2. Sharpness enhancement for clearer text
            sharpness_enhancer = ImageEnhance.Sharpness(img)
            img = sharpness_enhancer.enhance(1.2)
            
            # 3. Brightness adjustment if needed (avoid over-brightening)
            brightness_enhancer = ImageEnhance.Brightness(img)
            img = brightness_enhancer.enhance(1.05)
            
            # 4. Ensure optimal size for analysis
            original_size = img.size
            min_dimension = min(img.size)
            max_dimension = max(img.size)
            
            # Scale up small images for better readability
            if min_dimension < 400:
                scale_factor = 400 / min_dimension
                new_size = (int(img.size[0] * scale_factor), int(img.size[1] * scale_factor))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"Upscaled image from {original_size} to {new_size}")
            
            # Scale down very large images to manage file size
            elif max_dimension > 2000:
                scale_factor = 2000 / max_dimension
                new_size = (int(img.size[0] * scale_factor), int(img.size[1] * scale_factor))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"Downscaled image from {original_size} to {new_size}")
            
            # Create descriptive filename with metadata
            img_hash = hashlib.md5(image_bytes).hexdigest()[:8]
            img_path = os.path.join(output_dir, f"financial_img_{xref}_page{page_num+1}_{img_hash}.png")
            
            # Save with high quality settings
            img.save(img_path, "PNG", optimize=True, compress_level=6)
            
            print(f"Enhanced and saved image: {os.path.basename(img_path)} (size: {img.size})")
            return img_path, xref
            
        except Exception as e:
            print(f"Error processing image {xref}: {e}")
            return None, None
    
    def get_comprehensive_image_context(self, xref, page, text_blocks):
        """
        Simple context extraction focusing on text before and after images.
        Returns clean text content for efficient RAG retrieval.
        """
        try:
            img_rects = page.get_image_rects(xref)
            if not img_rects:
                return ""
            
            img_rect = img_rects[0]
            
            # Collect relevant text in proximity to image
            relevant_text = []
            
            for block in text_blocks:
                block_rect = fitz.Rect(block[:4])
                block_text = block[4].strip()
                
                if not block_text or len(block_text) < 3:
                    continue
                
                # Calculate distance from image
                img_center_y = (img_rect.y0 + img_rect.y1) / 2
                block_center_y = (block_rect.y0 + block_rect.y1) / 2
                vertical_distance = abs(img_center_y - block_center_y)
                
                # Include text that's close to the image (within reasonable distance)
                if vertical_distance <= 200:  # Adjust this threshold as needed
                    relevant_text.append({
                        'text': block_text,
                        'distance': vertical_distance,
                        'position': 'above' if block_center_y < img_center_y else 'below'
                    })
            
            # Sort by distance and build clean context
            relevant_text.sort(key=lambda x: x['distance'])
            
            # Take the closest 3-4 text blocks and create clean context
            context_parts = []
            for item in relevant_text[:4]:
                text = item['text']
                # Clean up the text
                if len(text) > 10 and text not in [part for part in context_parts]:
                    context_parts.append(text)
            
            # Join with proper spacing
            final_context = ". ".join(context_parts)
            
            # Limit context length for efficiency
            if len(final_context) > 800:
                words = final_context.split()
                final_context = " ".join(words[:120])
            
            return final_context
            
        except Exception as e:
            print(f"Error extracting context for image {xref}: {e}")
            return ""
    

    
    def get_preceeding_text(self, xref, page, text_blocks):
        """Get clean context text around image for efficient RAG retrieval."""
        return self.get_comprehensive_image_context(xref, page, text_blocks)
    
    def get_image_information(self):
        """
        Simplified image extraction with clean context text for efficient RAG retrieval.
        """
        image_details = {}
        output_path = os.path.splitext(self.pdf_path)[0]
        os.makedirs(output_path, exist_ok=True)
        
        pdf_document = self.get_pdf_data()
        total_images = 0
        processed_images = 0
        
        try:
            print(f"Processing PDF: {os.path.basename(self.pdf_path)}")
            
            # Process each page
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text_blocks = page.get_text("blocks")
                images = page.get_images(full=True)
                
                if not images:
                    continue
                
                total_images += len(images)
                print(f"Page {page_num + 1}: Found {len(images)} images")
                
                # Process each image on the page
                for img_info in images:
                    img_path, xref = self.save_images(img_info, page_num, pdf_document, output_path)
                    
                    if img_path and xref:
                        # Get clean context text around the image
                        context_text = self.get_comprehensive_image_context(xref, page, text_blocks)
                        image_details[img_path] = context_text
                        processed_images += 1
                        
                        # Log context length for debugging
                        print(f"  -> Image {processed_images}: Context length {len(context_text)} chars")
                    
            print(f"Successfully processed {processed_images}/{total_images} images")
            return image_details
            
        except Exception as e:
            print(f"Error during image extraction: {e}")
            return image_details
        finally:
            pdf_document.close()
    
    def encode_image(self,image_path):
        """
        Optimized image encoding with size management for API limits.
        """
        try:
            if not os.path.exists(image_path):
                return None
            
            # Check file size (OpenAI has 20MB limit)
            file_size = os.path.getsize(image_path)
            max_size = 20 * 1024 * 1024  # 20MB
            
            if file_size > max_size:
                # Compress large images
                img = Image.open(image_path)
                img_io = io.BytesIO()
                quality = max(60, int(100 * max_size / file_size))
                img.save(img_io, format='JPEG', quality=quality, optimize=True)
                img_bytes = img_io.getvalue()
            else:
                with open(image_path, "rb") as img_file:
                    img_bytes = img_file.read()
            
            return base64.b64encode(img_bytes).decode("utf-8")
            
        except Exception as e:
            print(f"Error encoding image {image_path}: {e}")
            return None

    def analyze_image_with_context(self, image_path, context_text):
        """
        Simple, efficient image analysis focused on extracting clean content for RAG.
        """
        if not os.path.exists(image_path):
            return "Error: Image file not found"
            
        try:
            image_base64 = self.encode_image(image_path)
            if not image_base64:
                return "Error: Failed to encode image"
            
            prompt = f"""
            You are analyzing a financial document image. The surrounding text context is:
            
            CONTEXT: {context_text}
            
            Please analyze this image and provide a CONCISE description that combines:
            1. What the image shows (chart type, visual elements)
            2. The key data/insights from the image
            3. How it relates to the surrounding text context
            
            Provide ONLY the essential information in 2-3 sentences. Focus on:
            - Chart/table type and main topic
            - Key numbers, percentages, or trends visible
            - Business context from surrounding text
            
            If this is a logo or decorative image, respond with: "INVALID_IMAGE"
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial document analyst. Provide concise, factual descriptions of charts and financial data images. Keep responses brief and focused on key insights."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                        ]
                    }
                ],
                max_tokens=300,  # Keep responses concise
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            
            # Skip invalid images
            if "INVALID_IMAGE" in result:
                return None
            
            return result
                
        except Exception as e:
            print(f"Error analyzing image {image_path}: {e}")
            return f"Error analyzing image: {str(e)}"
    

        
    
    def get_image_description(self, contexts):
        """Simple image description processing with clean output for efficient RAG."""
        image_analyses = {}
        output_file = os.path.splitext(self.pdf_path)[0] + "_analysis.json"
        
        print(f"Analyzing {len(contexts)} images...")
        processed_count = 0
        
        for image_path, context_text in contexts.items():
            try:
                print(f"Analyzing image: {os.path.basename(image_path)}")
                
                result = self.analyze_image_with_context(image_path, context_text)
                
                # Skip invalid images
                if result is None or "INVALID_IMAGE" in str(result):
                    print(f"Skipping non-financial image: {os.path.basename(image_path)}")
                    continue
                
                # Store clean result
                image_analyses[image_path] = result
                processed_count += 1
                print(f"  -> Processed successfully")
                
            except Exception as e:
                print(f"Error analyzing {image_path}: {e}")
                continue
        
        # Save simple analysis results
        analysis_data = {
            "pdf_source": self.pdf_path,
            "total_images_found": len(contexts),
            "successfully_analyzed": processed_count,
            "analysis_timestamp": str(datetime.now()),
            "image_analyses": image_analyses
        }
        
        with open(output_file, "w", encoding="utf-8") as json_file:
            json.dump(analysis_data, json_file, ensure_ascii=False, indent=2)
        
        print(f"Analysis complete: {processed_count}/{len(contexts)} images processed")
        print(f"Results saved to: {output_file}")
        return output_file

    def get_image_data(self,image_path,caption,company):
        """Fixed path handling for cross-platform compatibility."""
        try:
            # Use os.path.sep for cross-platform compatibility
            path_parts = image_path.replace("\\", "/").split("/")
            filename = path_parts[-1]
            
            # Extract page number more reliably
            if "_p" in filename:
                pagenumber = filename.split("_p")[1].split("_")[0]
            else:
                pagenumber = "1"  # fallback
            
            # Extract xref more reliably
            if "_" in filename:
                image_xref = filename.split("_")[1] if len(filename.split("_")) > 1 else "0"
            else:
                image_xref = "0"
            
            file_name = os.path.basename(self.pdf_path).replace(".pdf", "")
            image_source_in_file = f"{file_name}-page{pagenumber}-{image_xref}"
            
            image_metadata = {
                "source_file": self.pdf_path,
                "image_source_in_file": image_source_in_file,
                "image": image_path,
                "company": company,
                "type": "image",
                "page_num": pagenumber,
                "caption": caption 
            }
            return image_metadata
        except Exception as e:
            print(f"Error creating image metadata: {e}")
            return {
                "source_file": self.pdf_path,
                "image": image_path,
                "company": company,
                "type": "image",
                "caption": caption
            }

    def getRetriever(self,json_file_path, company):
        with open(json_file_path, "r", encoding="utf-8") as file:
            image_descriptions = json.load(file)     
        image_docs = []
        for image_path, caption in image_descriptions.items():
            image_metadata = self.get_image_data(image_path, caption, company)
            doc = Document(
                page_content=f"This is an image with the caption: {caption}",
                metadata=image_metadata
            )
            image_docs.append(doc)
        return image_docs