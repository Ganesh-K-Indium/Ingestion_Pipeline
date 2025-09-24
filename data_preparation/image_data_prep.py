import io
import os
import fitz
import json
import openai
import base64
from PIL import Image
from langchain.schema import Document

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
        This method is used to store the images in the folder.
        Args:
            img_info :- the coordinates of the image
            page_num :- Page number of the image
            pdf_document :- The fitz object of the pdf
            output_dir :- the output dir of the images
        Return:
            img_path :- the path of the image
            xref :- the x coordinate of the image
        """
        xref = img_info[0]
        base_image = pdf_document.extract_image(xref)
        image_bytes = base_image["image"]
        img = Image.open(io.BytesIO(image_bytes))
        img_path = os.path.join(output_dir,f"image{xref}-page{page_num+1}.png")
        img.save(img_path)
        return img_path,xref
    
    def get_preceeding_text(self,xref,page,text_blocks):
        """
        This method is used to get the preceding text of the image.
        Args:
            xref: the x reference of the image
            page: the page object of fitz having all information of content present in image
            text_blocks: the blocks of text
        """
        img_rect = page.get_image_rects(xref)[0]  
        preceding_text = ""        
        for block in sorted(text_blocks, key=lambda b: b[1], reverse=True):
            block_text = block[4].strip()
            block_y_position = block[1]
            if block_y_position < img_rect.y0 and block_text:
                preceding_text = block_text+" "+preceding_text
                if len(preceding_text.split(" "))>20 or "<image:" in preceding_text:
                    break
        return preceding_text
    
    def get_image_information(self):
        """
        This method is used for getting the information about the image like 
        the path of the image and preceding text.
        
        Args:
            None
        Return:
            image_info: the dictionary having image path and preceding text.
        """
        image_details = {}
        output_path = self.pdf_path.split(".pdf")[0]
        if not os.path.exists(output_path):
            os.mkdir(output_path)
        pdf_document = self.get_pdf_data()
        for page_num, _ in enumerate(pdf_document):
            page = pdf_document[page_num]
            text_blocks = page.get_text("blocks")
            images = page.get_images(full=True)
            if images:
                if len(images) == 1:
                    img_info = images[0]
                    img_path, xref = self.save_images(img_info,page_num,pdf_document,output_path)
                    preceding_text = self.get_preceeding_text(xref,page,text_blocks)
                    image_details[img_path] = preceding_text
                else:
                    for _, img_info in enumerate(images):
                        img_path, xref = self.save_images(img_info,page_num,
                                                          pdf_document,output_path)
                        preceding_text = self.get_preceeding_text(xref,page,text_blocks)
                        image_details[img_path] = preceding_text
        return image_details
    
    def encode_image(self,image_path):
        """
        This method is used for encoding the image into base64
        Args:
            image_path : The path of the image
        Return:
            Encoded image
        """
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    def analyze_image_with_context(self,image_path, context_text):
        """
        Analyzes financial document images and extracts structured data.
        Args:
            image_path: Path to the image file
            context_text: Surrounding text context
        Returns:
            str: JSON formatted analysis or error message
        """
        if not os.path.exists(image_path):
            return json.dumps({"error": "File not found", "path": image_path})
            
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            return json.dumps({"error": "API key missing"})
            
        try:
            image_base64 = self.encode_image(image_path)
            
            prompt = f"""
            Analyze this financial image with context: {context_text}

            Required JSON format:
            {{
                "title": "Brief, accurate title",
                "type": "chart/table/graph/diagram/logo",
                "data": {{
                    "dates": ["All dates/periods"],
                    "values": ["All numbers with units"],
                    "percentages": ["All % changes"],
                    "trends": ["Trends with numbers"]
                }},
                "analysis": {{
                    "main_point": "Key finding",
                    "details": ["Specific insights with numbers"],
                    "significance": "high/medium/low"
                }}
            }}

            For logos/signatures: {{"type": "INVALID"}}

            Extract ALL numbers, dates, and trends exactly as shown.
            Include specific values for all trends and changes.
            """

            response = openai.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial data extraction expert. Extract ALL numerical data precisely."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                        ]
                    }
                ],
                max_tokens=500
            )
            
            result = response.choices[0].message.content
            
            # Validate JSON response
            try:
                json.loads(result)
                return result
            except json.JSONDecodeError:
                return json.dumps({
                    "error": "Invalid response",
                    "raw_content": result
                })
                
        except Exception as e:
            return json.dumps({
                "error": "Processing failed",
                "message": str(e)
            })
        
        prompt = f"""
        ## **Context-Aware Financial Image Analysis**

        **Task:**  
        You are an advanced data analyst. Analyze the given image fully — extract all numbers, trends, and patterns. The preceding text provides context about what the image is related to:

        **Context (Preceding Text):**  
        ```  
        {context_text}
        ```   
        ### Your Task:
        1. **Extract all data** from the image (e.g., values, years, trends etc).
        2. **Identify key insights** — upward/downward trends, comparisons between lines/groups, spikes, drops, etc.
        3. **Connect the analysis to the context** — make the description meaningful and connected to the text.
        4. **Generate a final summary** in clear, professional language.

        **Output Format:**  
        - Identified Matching Text as title of image: whatever portion of proceeding text matching to the image, have it as a title.
        - Description: detail description of the image by complete analysis of the image along with all numbers, trend or all important information available in the image

        Ensure the analysis is thorough and insightful — don’t miss any data points!

        if the image is related to any signature or logo then simply generate the below response.
        **INVALID IMAGE**
        """

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a document analysis assistant."},
                {"role": "user", "content": prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Here’s the image:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]}
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    
    def get_image_description(self,contexts):
        image_caption = {}
        output_file = self.pdf_path.split(".pdf")[0]+".json"
        for image_path, context_text in contexts.items():
            result = self.analyze_image_with_context(image_path, context_text)
            if "INVALID IMAGE" in result:
                continue
            image_caption[image_path] = result
        with open(output_file, "w", encoding="utf-8") as json_file:
            json.dump(image_caption, json_file, ensure_ascii=False, indent=4)
        return output_file

    def get_image_data(self,image_path,caption,company):
        pagenumber = image_path.split("page")[-1].split(".png")[0]
        image_xref = image_path.split("\\")[-1].split("-")[0]
        file_name = self.pdf_path.split("\\")[-1][:-4]
        image_source_in_file = f"{file_name}-page{pagenumber}-{image_xref}"
        image_metadata = {
            "source_file": self.pdf_path,
            "image_source_in_file": image_source_in_file,
            "image": image_path,
            "company":company,
            "type": "image",
            "page_num": pagenumber,
            "caption": caption 
        }
        return image_metadata

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