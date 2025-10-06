"""
LangGraph + GPT-4.1 Agent using Jira MCP HTTP Streaming Server (fixed)
----------------------------------------------------------------------
Connects to FastMCP Jira Operations server using streamable HTTP transport.
"""

import asyncio
import aiohttp
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from dotenv import load_dotenv

load_dotenv()


async def wait_for_server(url: str, timeout: int = 10):
    """Wait until the MCP server is ready to accept connections."""
    import time
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status in (200, 404):  # 404 is fine, stream endpoint doesn't return JSON
                        print(f"✅ MCP server is up at {url}")
                        return True
        except aiohttp.ClientConnectionError:
            await asyncio.sleep(1)
    raise TimeoutError(f"MCP server at {url} did not respond within {timeout} seconds")


async def main():
    # ------------------------------------------------------------
    # 1️⃣ Model
    # ------------------------------------------------------------
    model = ChatOpenAI(model="gpt-4.1", temperature=0)

    # ------------------------------------------------------------
    # 2️⃣ Streamable HTTP URL — must end with `/stream`
    # ------------------------------------------------------------
    MCP_HTTP_STREAM_URL = "http://localhost:8000/mcp"
    #await wait_for_server("http://localhost:8000")

    # ------------------------------------------------------------
    # 3️⃣ Connect to MCP stream endpoint (triple unpack)
    # ------------------------------------------------------------
    async with streamablehttp_client(MCP_HTTP_STREAM_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("✅ MCP Client Session initialized")

            # --------------------------------------------------------
            # 4️⃣ Load MCP tools dynamically
            # --------------------------------------------------------
            tools = await load_mcp_tools(session)
            print(f"✅ Loaded {len(tools)} Jira MCP tools via HTTP stream")

            # --------------------------------------------------------
            # 5️⃣ Create LangGraph ReAct Agent
            # --------------------------------------------------------
            agent = create_react_agent(
                model=model,
                tools=tools,
                name="JiraLangGraphAgent"
            )

            # --------------------------------------------------------
            # 6️⃣ Run a test query
            # --------------------------------------------------------
            user_prompt = "download and ingest attachments for issue test-1"
            print(f"\n🧠 Running agent with prompt:\n{user_prompt}\n")

            response = await agent.ainvoke({"messages": user_prompt})
            print("\n🤖 Agent Response:\n", response)


if __name__ == "__main__":
    asyncio.run(main())
