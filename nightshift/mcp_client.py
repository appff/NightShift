import asyncio
import json
import logging
import threading
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

class MCPClient:
    def __init__(self, name: str, command: str, args: List[str]):
        self.name = name
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None
        )
        self.session: Optional[ClientSession] = None
        self._client_context = None
        self.tools = []

    async def connect(self):
        if not HAS_MCP:
            return
        try:
            self._client_context = stdio_client(self.server_params)
            read, write = await self._client_context.__aenter__()
            self.session = ClientSession(read, write)
            await self.session.__aenter__()
            await self.session.initialize()
            
            # List tools
            result = await self.session.list_tools()
            self.tools = result.tools
            logging.info(f"✅ Connected to MCP server '{self.name}' with {len(self.tools)} tools.")
        except Exception as e:
            logging.error(f"❌ Failed to connect to MCP server '{self.name}': {e}")
            self.session = None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if not self.session:
            return f"Error: MCP server '{self.name}' is not connected."
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            # result is a CallToolResult
            text_parts = []
            for content in result.content:
                if content.type == "text":
                    text_parts.append(content.text)
                elif content.type == "resource":
                    text_parts.append(f"[Resource: {content.resource}]")
                elif content.type == "image":
                    text_parts.append("[Image Content]")
            
            if result.isError:
                return f"MCP Tool Error: " + "\n".join(text_parts)
            return "\n".join(text_parts)
        except Exception as e:
            logging.error(f"❌ Error calling tool '{tool_name}' on '{self.name}': {e}")
            return f"Error executing MCP tool '{tool_name}': {e}"

    async def disconnect(self):
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if self._client_context:
                await self._client_context.__aexit__(None, None, None)
        except:
            pass

class MCPManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.clients: Dict[str, MCPClient] = {}
        self.enabled = HAS_MCP and bool(config)
        self.loop = None
        self.thread = None
        
        if self.enabled:
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self.thread.start()

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start(self):
        if not self.enabled:
            if not HAS_MCP and self.config:
                logging.warning("⚠️ MCP servers configured but 'mcp' SDK is not installed.")
            return

        futures = []
        for name, server_cfg in self.config.items():
            if not isinstance(server_cfg, dict) or not server_cfg.get("enabled", True):
                continue
            
            cmd = server_cfg.get("command")
            if not cmd: continue
            
            client = MCPClient(name, cmd, server_cfg.get("args", []))
            self.clients[name] = client
            futures.append(asyncio.run_coroutine_threadsafe(client.connect(), self.loop))
        
        # Wait for all connections to complete (with timeout)
        for f in futures:
            try:
                f.result(timeout=30)
            except Exception as e:
                logging.error(f"Timeout or error connecting to an MCP server: {e}")

    def get_tool_definitions(self) -> str:
        """Returns a string description of all available tools for prompt injection."""
        if not self.clients:
            return ""
            
        definitions = []
        for name, client in self.clients.items():
            if not client.session:
                continue
            
            # Map client names to logical categories for the LLM
            category = "GENERAL"
            if "thinking" in name.lower(): category = "REASONING"
            elif "serena" in name.lower(): category = "MEMORY & LSP"
            elif "context" in name.lower(): category = "DOCUMENTATION"
            
            definitions.append(f"\n[{category} TOOLS - Provided by {name}]")
            for tool in client.tools:
                # Add a 'proactive' hint to certain tools
                desc = tool.description
                if category == "REASONING":
                    desc = f"[STRONGLY RECOMMENDED] {desc}. Use this proactively for complex architectural decisions."
                elif "memory" in tool.name.lower():
                    desc = f"[CONTEXTUAL] {desc}. Use this to check past project decisions or save new insights."
                
                definitions.append(f"- {tool.name}: {desc}")
                definitions.append(f"  Usage: mcp_run {tool.name} <json_args>")
                if tool.inputSchema:
                    props = tool.inputSchema.get("properties", {})
                    if props:
                        definitions.append(f"  Args: {list(props.keys())}")
        
        if not definitions:
            return ""
        
        header = "\n[ADVANCED COGNITIVE TOOLS (MCP)]\nThese tools extend your intelligence and memory. Use them proactively whenever a task involves complex logic, missing context, or long-term decision making.\n"
        footer = "\nExample: mcp_run search_memory {\"query\": \"how to use docker\"}\n"
        return header + "\n".join(definitions) + footer

    def call_tool(self, tool_name: str, arguments_json: str) -> str:
        """Synchronous wrapper to call an MCP tool."""
        if not self.enabled:
            return "Error: MCP Manager is not enabled or SDK is missing."

        # Find which client has this tool
        target_client = None
        for client in self.clients.values():
            if any(t.name == tool_name for t in client.tools):
                target_client = client
                break
        
        if not target_client:
            return f"Error: Tool '{tool_name}' not found in any connected MCP server."

        try:
            if isinstance(arguments_json, str):
                # Clean up potential markdown formatting if LLM included it
                clean_json = arguments_json.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```(?:json)?\n", "", clean_json)
                    clean_json = re.sub(r"\n```$", "", clean_json)
                args = json.loads(clean_json)
            else:
                args = arguments_json
        except Exception as e:
            return f"Error parsing JSON arguments for MCP tool: {e}\nInput was: {arguments_json}"

        future = asyncio.run_coroutine_threadsafe(
            target_client.call_tool(tool_name, args), self.loop
        )
        try:
            return future.result(timeout=60)
        except Exception as e:
            return f"Error: MCP tool execution timed out or failed: {e}"

    def stop(self):
        if not self.loop: return
        futures = [asyncio.run_coroutine_threadsafe(c.disconnect(), self.loop) for c in self.clients.values()]
        for f in futures:
            try: f.result(timeout=5)
            except: pass
        self.loop.call_soon_threadsafe(self.loop.stop)
