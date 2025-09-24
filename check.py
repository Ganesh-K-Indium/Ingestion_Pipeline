import asyncio
from fastmcp import Client

client = Client("http://127.0.0.1:8002")

async def main():
    async with client:
        await client.ping()
        tools = await client.list_tools()
        print("Available tools:", tools)

        result = await client.call_tool("ingest_local", {"file_name": "META.pdf"})
        print("Result:", result)

asyncio.run(main())
