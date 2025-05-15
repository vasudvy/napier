#!/usr/bin/env python3
import asyncio
import sys
import os
import json
import time
import threading
import subprocess
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
import google.generativeai as genai
from rich.console import Console
from rich.markdown import Markdown
from rich import print as rprint
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live

# Load environment variables from .env file
load_dotenv()

# Initialize Rich console for better terminal output
console = Console()

class NapierConfig:
    """
    Class to handle Napier configuration from JSON file
    """
    def __init__(self, config_path: str = None):
        """
        Initialize Napier config
        
        Args:
            config_path: Path to napier_config.json file (optional)
        """
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'napier_config.json')
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            else:
                console.print(f"[yellow]Config file not found at {self.config_path}. Using default configuration.[/yellow]")
                return {
                    "mcpServers": {},
                    "defaults": {},
                    "napier": {
                        "model": "gemini-2.0-flash",
                        "api_config": {"temperature": 0.2}
                    }
                }
        except Exception as e:
            console.print(f"[bold red]Error loading config: {str(e)}[/bold red]")
            return {
                "mcpServers": {},
                "defaults": {},
                "napier": {
                    "model": "gemini-2.0-flash",
                    "api_config": {"temperature": 0.2}
                }
            }
    
    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific MCP server"""
        servers = self.config.get("mcpServers", {})
        return servers.get(server_name)
    
    def get_default_server(self) -> Optional[str]:
        """Get default MCP server name"""
        return self.config.get("defaults", {}).get("server")
    
    def get_napier_config(self) -> Dict[str, Any]:
        """Get Napier-specific configuration"""
        return self.config.get("napier", {})
    
    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """List all configured MCP servers"""
        return self.config.get("mcpServers", {})

class ThinkingAnimation:
    """Class to display a thinking animation while waiting for a response"""
    def __init__(self, message="Thinking"):
        self.message = message
        self.spinner = Spinner("dots", text=message)
        self.live = Live(self.spinner, refresh_per_second=10)
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the thinking animation"""
        self.running = True
        self.live.start()
        
    def stop(self):
        """Stop the thinking animation"""
        self.running = False
        self.live.stop()

class NapierClient:
    """
    Napier - An MCP client that connects AI models with third-party applications.
    Currently supports Gemini model integration.
    """
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        # Initialize Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            console.print("[bold red]Error: GEMINI_API_KEY not found in environment variables.[/bold red]")
            console.print("[yellow]Please create a .env file with your GEMINI_API_KEY=[/yellow]")
            sys.exit(1)
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Conversation history
        self.chat_history = []
        self.connected_server = None
        
        # System prompt for Gemini
        self.system_prompt = """You are a helpful AI assistant in the Napier terminal application.
You can help users with various tasks and answer questions.
When you're connected to MCP servers, you can use tools to interact with third-party applications.
Be concise, helpful, and friendly in your responses."""
    
    async def initialize_playwright(self):
        """Initialize Playwright with browser installation"""
        console.print("[yellow]Initializing Playwright and installing browsers...[/yellow]")
        
        # Create a thinking animation
        thinking = ThinkingAnimation("Installing Playwright browsers")
        thinking.start()
        
        try:
            # Run the browser installation command
            result = subprocess.run(
                ["playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                check=True
            )
            thinking.stop()
            console.print("[green]Successfully installed Playwright browsers![/green]")
            return True
        except subprocess.CalledProcessError as e:
            thinking.stop()
            console.print(f"[bold red]Error installing Playwright browsers: {e.stderr}[/bold red]")
            return False
        except Exception as e:
            thinking.stop()
            console.print(f"[bold red]Error during Playwright initialization: {str(e)}[/bold red]")
            return False
    
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        # Store the server path
        self.connected_server = server_script_path
        
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,          # Python or Node interpreter
            args=[server_script_path], # Path to server script
            env=None                  # Use current environment
        )

        try:
            console.print(f"[yellow]Connecting to MCP server: {server_script_path}...[/yellow]")
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

            # Initialize the session
            await self.session.initialize()

            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            tool_names = [tool.name for tool in tools]
            
            console.print(f"[green]Successfully connected to server![/green]")
            console.print(Panel(
                f"[bold]Available tools:[/bold]\n" + "\n".join([f"• {name}" for name in tool_names]),
                title="MCP Server Connection",
                border_style="green"
            ))
            
            return tool_names
        except Exception as e:
            console.print(f"[bold red]Error connecting to server: {str(e)}[/bold red]")
            return None
    
    async def connect_to_server_from_config(self, server_name: str):
        """Connect to an MCP server defined in the configuration file
        
        Args:
            server_name: Name of the server in the mcpServers config section
        """
        config = NapierConfig()
        server_config = config.get_server_config(server_name)
        
        if not server_config:
            console.print(f"[bold red]Error: Server '{server_name}' not found in configuration.[/bold red]")
            return None
        
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env")
        
        # Store the server name
        self.connected_server = server_name
        
        # Create server parameters
        from mcp import StdioServerParameters
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )

        try:
            console.print(f"[yellow]Connecting to MCP server: {server_name}...[/yellow]")
            
            # Connect using stdio transport
            from mcp.client.stdio import stdio_client
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            
            from mcp import ClientSession
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

            # Initialize the session
            await self.session.initialize()

            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            tool_names = [tool.name for tool in tools]
            
            console.print(f"[green]Successfully connected to server: {server_name}![/green]")
            console.print(Panel(
                f"[bold]Available tools:[/bold]\n" + "\n".join([f"• {name}" for name in tool_names]),
                title=f"MCP Server: {server_name}",
                border_style="green"
            ))
            
            # Automatically initialize Playwright if it's the Playwright server
            if server_name.lower() == "playwright":
                await self.initialize_playwright()
            
            return tool_names
        except Exception as e:
            console.print(f"[bold red]Error connecting to server: {str(e)}[/bold red]")
            return None
    
    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""
        if not self.session:
            return "Error: Not connected to any MCP server. Use 'connect' command first."
        
        # Add user query to history
        self.chat_history.append({"role": "user", "parts": [query]})
        
        # Get available tools from the server
        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        
        # Format tools for Gemini
        tools_description = "You have access to the following tools:\n\n"
        for tool in available_tools:
            tools_description += f"- {tool['name']}: {tool['description']}\n"
            tools_description += f"  Input schema: {json.dumps(tool['input_schema'], indent=2)}\n\n"
        
        # Prepare prompt with instructions and tools
        system_prompt = f"""You are an AI assistant that helps users interact with various applications through tools.
{tools_description}

INSTRUCTIONS:
1. Analyze the user's request carefully.
2. If a tool is needed to fulfill the request, decide which tool to use.
3. Format your tool calls as JSON, wrapped in triple backticks with the 'json' tag.
4. Example tool call format:
```json
{{
  "tool_name": "tool_name_here",
  "parameters": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}
```
5. After receiving tool results, provide a helpful response that incorporates the information.
6. If no tool is needed, respond directly to the user's request.

Always make sure to follow the exact input schema for each tool when making a call."""

        # Create and start thinking animation
        thinking = ThinkingAnimation()
        thinking.start()
        
        try:
            # Initialize Gemini chat
            chat = self.model.start_chat(history=self.chat_history)
            
            # Send the query along with system prompt
            response = chat.send_message(
                [system_prompt, query],
                generation_config={"temperature": 0.2}
            )
            
            response_text = response.text
            self.chat_history.append({"role": "model", "parts": [response_text]})
            
            # Process tool calls in response
            import re
            tool_call_pattern = r"```json\s*(\{[^`]*\})\s*```"
            tool_calls = re.findall(tool_call_pattern, response_text)
            
            final_response = []
            
            if tool_calls:
                for tool_call_json in tool_calls:
                    try:
                        tool_call = json.loads(tool_call_json)
                        tool_name = tool_call.get("tool_name")
                        parameters = tool_call.get("parameters", {})
                        
                        thinking.stop()  # Stop thinking animation to show tool execution
                        console.print(f"[bold cyan]Executing tool:[/bold cyan] {tool_name}")
                        console.print(f"[cyan]Parameters:[/cyan] {json.dumps(parameters, indent=2)}")
                        
                        # Start thinking animation for tool execution
                        tool_thinking = ThinkingAnimation(f"Executing {tool_name}")
                        tool_thinking.start()
                        
                        # Execute tool call
                        result = await self.session.call_tool(tool_name, parameters)
                        tool_thinking.stop()
                        
                        # Clean up the tool result, especially for Playwright
                        result_content = self._clean_tool_output(tool_name, result.content)
                        
                        # Format tool result for display
                        result_str = f"\n[Tool Result]\n{result_content}\n"
                        final_response.append(result_str)
                        
                        # Send tool result back to Gemini
                        thinking.start()  # Restart thinking animation for follow-up
                        followup_system_prompt = f"""The tool '{tool_name}' returned the following result:

{result.content}

Please analyze this result and provide a helpful response to the user based on this information.
Keep your response focused on the insights from the tool result."""

                        followup_response = chat.send_message(followup_system_prompt)
                        final_response.append(followup_response.text)
                        self.chat_history.append({"role": "model", "parts": [followup_response.text]})
                        
                    except json.JSONDecodeError:
                        console.print(f"[bold red]Error: Invalid JSON format in tool call[/bold red]")
                        final_response.append("Error: Invalid tool call format detected.")
                    except Exception as e:
                        console.print(f"[bold red]Error executing tool: {str(e)}[/bold red]")
                        final_response.append(f"Error executing tool: {str(e)}")
                
                thinking.stop()  # Stop thinking animation before final response
                return "\n".join(final_response)
            else:
                # No tool calls, just return the response
                thinking.stop()  # Stop thinking animation
                return response_text
                
        except Exception as e:
            thinking.stop()  # Make sure to stop animation on error
            console.print(f"[bold red]Error: {str(e)}[/bold red]")
            return f"Error processing query: {str(e)}"
    
    def _clean_tool_output(self, tool_name: str, output: str) -> str:
        """Clean and format tool output for better display"""
        if "playwright" in tool_name.lower():
            # Try to extract the most relevant information from Playwright output
            import re
            
            # Remove noisy HTML, XML, or markdown tags
            output = re.sub(r'```(?:html|xml|markdown|)\n', '', output)
            output = re.sub(r'```', '', output)
            
            # Try to extract useful content from Playwright operations
            if "screenshot" in tool_name.lower():
                return "Screenshot captured successfully."
                
            if "navigate" in tool_name.lower() or "goto" in tool_name.lower():
                return f"Navigated to the requested page successfully."
                
            if "click" in tool_name.lower():
                return "Clicked on the specified element."
                
            if "get" in tool_name.lower() and "content" in tool_name.lower():
                # For content extraction, try to keep it clean but informative
                # Remove any leading/trailing whitespace and limit length
                output = output.strip()
                if len(output) > 1000:
                    output = output[:997] + "..."
                
            # For other Playwright operations, provide a generic clean response
            if len(output.strip()) == 0:
                return "Operation completed successfully."
        
        return output

    async def chat_with_gemini(self, query: str) -> str:
        """Chat directly with Gemini without using MCP tools"""
        # Add user query to history
        self.chat_history.append({"role": "user", "parts": [query]})
        
        # Create and start thinking animation
        thinking = ThinkingAnimation()
        thinking.start()
        
        try:
            # Initialize Gemini chat with system prompt
            chat = self.model.start_chat(history=self.chat_history)
            
            # Send the query with system prompt
            response = chat.send_message(
                [self.system_prompt, query],
                generation_config={"temperature": 0.7}
            )
            
            response_text = response.text
            self.chat_history.append({"role": "model", "parts": [response_text]})
            
            thinking.stop()  # Stop thinking animation
            return response_text
                
        except Exception as e:
            thinking.stop()  # Make sure to stop animation on error
            console.print(f"[bold red]Error: {str(e)}[/bold red]")
            return f"Error: {str(e)}"
            
    async def list_tools(self):
        """List available tools from connected MCP servers"""
        if not self.session:
            return "Not connected to any MCP server. Use '/connect <path_to_server>' first."
            
        response = await self.session.list_tools()
        tools = response.tools
        
        result = "Available MCP Tools:\n\n"
        for tool in tools:
            result += f"• {tool.name}: {tool.description}\n"
            
        return result
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        welcome_message = """
        █▄░█ ▄▀█ █▀█ █ █▀▀ █▀█
        █░▀█ █▀█ █▀▀ █ ██▄ █▀▄
        
        Model Context Protocol Client
        
        Commands:
        • '/connect <path_to_server>' - Connect to an MCP server
        • '/connect-server <server_name>' - Connect to a configured MCP server
        • '/servers' - List configured MCP servers
        • '/tools' - List available MCP tools
        • '/help' - Show help information
        • '/exit' or '/quit' - Exit the application
        
        Start chatting directly with Napier!
        """
        console.print(Panel(welcome_message, border_style="blue"))

        while True:
            try:
                if self.connected_server:
                    prompt = f"[bold blue]Napier[/bold blue] ({self.connected_server}) > "
                else:
                    prompt = "[bold blue]Napier[/bold blue] > "
                    
                user_input = Prompt.ask(prompt)
                
                if user_input.lower() in ['/exit', '/quit']:
                    console.print("[yellow]Exiting Napier...[/yellow]")
                    break
                
                elif user_input.lower().startswith('/connect '):
                    server_path = user_input[9:].strip()
                    await self.connect_to_server(server_path)
                
                elif user_input.lower().startswith('/connect-server '):
                    server_name = user_input[16:].strip()
                    await self.connect_to_server_from_config(server_name)
                    
                elif user_input.lower() == '/servers':
                    config = NapierConfig()
                    servers = config.list_servers()
                    
                    if not servers:
                        console.print("[yellow]No MCP servers configured. Add servers to napier_config.json.[/yellow]")
                    else:
                        servers_info = "Configured MCP Servers:\n\n"
                        for name, cfg in servers.items():
                            command = cfg.get("command", "N/A")
                            args = " ".join(cfg.get("args", []))
                            servers_info += f"• {name}: {command} {args}\n"
                        
                        console.print(Panel(servers_info, title="MCP Servers", border_style="green"))
                    
                elif user_input.lower() == '/tools':
                    tools_info = await self.list_tools()
                    console.print(Panel(tools_info, title="Available Tools", border_style="green"))
                    
                elif user_input.lower() == '/help':
                    help_text = """
                    Available commands:
                    • '/connect <path_to_server>' - Connect to an MCP server
                    • '/connect-server <server_name>' - Connect to a configured MCP server
                    • '/servers' - List configured MCP servers
                    • '/tools' - List available MCP tools
                    • '/help' - Display this help message
                    • '/exit' or '/quit' - Exit the application
                    
                    Chat directly with Napier or use MCP tools when connected
                    • Type normally to chat with Napier
                    • Type '/use <tool_name>' to specifically use an MCP tool
                    """
                    console.print(Panel(help_text, title="Napier Help", border_style="green"))
                    
                elif user_input.lower().startswith('/use ') and user_input.strip() != '/use':
                    if not self.session:
                        console.print("[bold yellow]Not connected to any MCP server. Use '/connect <path_to_server>' first.[/bold yellow]")
                        continue
                        
                    # Extract tool name and query
                    parts = user_input[5:].strip().split(' ', 1)
                    if len(parts) < 2:
                        console.print("[bold yellow]Please provide a query to use with the tool.[/bold yellow]")
                        continue
                        
                    tool_name = parts[0]
                    query = f"I want to use the '{tool_name}' tool to {parts[1]}"
                        
                    response = await self.process_query(query)
                    # Print the response directly without a panel
                    console.print(Markdown(response))
                
                elif user_input.strip() and user_input.startswith('/'):
                    console.print("[bold yellow]Unknown command. Type '/help' for assistance.[/bold yellow]")
                
                elif user_input.strip():
                    # Check if connected to MCP server and use it if available
                    if self.session:
                        response = await self.process_query(user_input)
                    else:
                        # Direct chat with Gemini
                        response = await self.chat_with_gemini(user_input)
                        
                    # Print the response directly without a panel
                    console.print(Markdown(response))
                    
            except Exception as e:
                console.print(f"[bold red]Error: {str(e)}[/bold red]")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
        console.print("[green]Resources cleaned up.[/green]")

async def main():
    """Main entry point"""
    # Display ASCII art banner
    banner = """
    ███╗   ██╗ █████╗ ██████╗ ██╗███████╗██████╗ 
    ████╗  ██║██╔══██╗██╔══██╗██║██╔════╝██╔══██╗
    ██╔██╗ ██║███████║██████╔╝██║█████╗  ██████╔╝
    ██║╚██╗██║██╔══██║██╔═══╝ ██║██╔══╝  ██╔══██╗
    ██║ ╚████║██║  ██║██║     ██║███████╗██║  ██║
    ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝
    """
    console.print(Panel(banner, border_style="blue"))
    console.print("[bold]Napier[/bold] - Chat with AI and connect to third-party apps")
    console.print("Type '/help' for available commands")
    console.print("Version 1.0.0\n")

    client = NapierClient()
    try:
        # If a server path is provided as an argument, connect to it
        if len(sys.argv) > 1:
            await client.connect_to_server(sys.argv[1])
        
        # Start the chat loop
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Keyboard interrupt detected. Exiting Napier...[/yellow]")