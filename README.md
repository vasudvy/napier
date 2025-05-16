// Project structure
// 
// /src
// ├── components
// │   ├── ChatInput.tsx
// │   ├── ChatMessage.tsx
// │   ├── CommandBar.tsx
// │   ├── ServerConnection.tsx
// │   └── ThinkingIndicator.tsx
// ├── hooks
// │   ├── useGemini.ts
// │   └── useMcpClient.ts
// ├── types
// │   ├── config.ts
// │   ├── chat.ts
// │   └── mcp.ts
// ├── utils
// │   ├── config.ts
// │   └── commandParser.ts
// ├── App.tsx
// └── main.tsx
// 
// /public
// └── napier_config.json


// Types for Napier configuration
export interface NapierConfig {
  mcpServers: Record<string, McpServerConfig>;
  inputs?: ConfigInput[];
  defaults: {
    server?: string;
  };
  napier: {
    model: string;
    api_config: {
      temperature: number;
      [key: string]: any;
    };
  };
}

export interface McpServerConfig {
  command: string;
  args: string[];
  env?: Record<string, string>;
}

export interface ConfigInput {
  type: string;
  id: string;
  description: string;
  password: boolean;
}

// Types for chat system
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isToolResult?: boolean;
  toolName?: string;
}

export interface ToolCall {
  tool_name: string;
  parameters: Record<string, any>;
}

export interface ToolResponse {
  content: string;
  status: 'success' | 'error';
}

// Types for MCP client
export interface McpTool {
  name: string;
  description: string;
  inputSchema: Record<string, any>;
}

export interface McpResource {
  uri: string;
  description?: string;
}

export interface McpPrompt {
  name: string;
  description?: string;
  arguments?: Record<string, any>;
}

export interface McpSession {
  initialize: () => Promise<void>;
  listTools: () => Promise<{ tools: McpTool[] }>;
  callTool: (name: string, parameters: Record<string, any>) => Promise<{ content: string }>;
  listResources: () => Promise<{ resources: McpResource[] }>;
  readResource: (params: { uri: string }) => Promise<{ content: string }>;
  listPrompts: () => Promise<{ prompts: McpPrompt[] }>;
  getPrompt: (params: { name: string, arguments?: Record<string, any> }) => Promise<{ content: string }>;
}

export interface McpTransport {
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
}

import { useState, useCallback, useEffect } from 'react';
import { McpTool, McpSession } from '../types/mcp';
import { McpServerConfig } from '../types/config';
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

// For web-based implementations, we need to use HTTP transport
// This may need to be adjusted based on your backend architecture

export function useMcpClient() {
  const [client, setClient] = useState<Client | null>(null);
  const [session, setSession] = useState<McpSession | null>(null);
  const [tools, setTools] = useState<McpTool[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectedServer, setConnectedServer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  const connectToServer = useCallback(async (serverConfig: McpServerConfig, serverName: string) => {
    if (isConnecting) return;
    
    setIsConnecting(true);
    setError(null);
    
    try {
      // In a web context, we need a backend to proxy the MCP server
      // We'll simulate this with a simple HTTP connection to a hypothetical backend endpoint
      const baseUrl = new URL(`/api/mcp/servers/${serverName}`, window.location.origin);
      
      const newClient = new Client({
        name: 'napier-web-client',
        version: '1.0.0'
      });
      
      let connected = false;
      
      // Try modern transport first
      try {
        const transport = new StreamableHTTPClientTransport(baseUrl);
        await newClient.connect(transport);
        connected = true;
        console.log("Connected using Streamable HTTP transport");
      } catch (transportError) {
        console.log("Streamable HTTP connection failed, falling back to SSE transport");
        
        // Fall back to SSE transport
        try {
          const sseTransport = new SSEClientTransport(baseUrl);
          await newClient.connect(sseTransport);
          connected = true;
          console.log("Connected using SSE transport");
        } catch (sseError) {
          throw new Error(`Failed to connect using available transports: ${sseError}`);
        }
      }
      
      if (!connected) {
        throw new Error("Failed to establish connection with MCP server");
      }
      
      // Store the client
      setClient(newClient);
      setSession(newClient as unknown as McpSession);
      setConnectedServer(serverName);
      setIsConnected(true);
      
      // Fetch available tools
      const response = await newClient.listTools();
      setTools(response.tools);
      
      return response.tools;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Failed to connect to server: ${message}`);
      return null;
    } finally {
      setIsConnecting(false);
    }
  }, [isConnecting]);

  const disconnectFromServer = useCallback(async () => {
    if (client) {
      try {
        // In a real implementation, you would disconnect the transport
        // Since we're simulating, we'll just reset state
        setClient(null);
        setSession(null);
        setTools([]);
        setIsConnected(false);
        setConnectedServer(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(`Failed to disconnect: ${message}`);
      }
    }
  }, [client]);

  const callTool = useCallback(async (toolName: string, parameters: Record<string, any>) => {
    if (!session) {
      throw new Error("Not connected to any MCP server");
    }
    
    try {
      return await session.callTool(toolName, parameters);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Error executing tool: ${message}`);
      throw err;
    }
  }, [session]);

  const listTools = useCallback(async () => {
    if (!session) {
      throw new Error("Not connected to any MCP server");
    }
    
    try {
      const response = await session.listTools();
      setTools(response.tools);
      return response.tools;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Error listing tools: ${message}`);
      throw err;
    }
  }, [session]);

  // Clean up connection on unmount
  useEffect(() => {
    return () => {
      disconnectFromServer();
    };
  }, [disconnectFromServer]);

  return {
    connectToServer,
    disconnectFromServer,
    callTool,
    listTools,
    isConnected,
    connectedServer,
    tools,
    error,
    isConnecting
  };
}

import { useState, useCallback } from 'react';
import { ChatMessage, ToolCall } from '../types/chat';

// This is a simplified hook for interfacing with Gemini API in a web context
// In a real implementation, you'd use the Gemini JS SDK or API directly

export function useGemini(apiKey: string) {
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const systemPrompt = `You are a helpful AI assistant in the Napier web application.
You can help users with various tasks and answer questions.
When you're connected to MCP servers, you can use tools to interact with third-party applications.
Be concise, helpful, and friendly in your responses.`;

  // Process a query using the Gemini API
  const processQuery = useCallback(async (
    query: string, 
    history: ChatMessage[],
    availableTools: any[] = []
  ): Promise<{response: string, toolCalls: ToolCall[] | null}> => {
    setIsThinking(true);
    setError(null);
    
    try {
      // Format the chat history for the API
      const formattedHistory = history
        .filter(msg => msg.role !== 'system')
        .map(msg => ({
          role: msg.role,
          parts: [{ text: msg.content }]
        }));
      
      // Prepare tools description if tools are available
      let toolsDescription = "";
      if (availableTools.length > 0) {
        toolsDescription = "You have access to the following tools:\n\n";
        for (const tool of availableTools) {
          toolsDescription += `- ${tool.name}: ${tool.description}\n`;
          toolsDescription += `  Input schema: ${JSON.stringify(tool.inputSchema, null, 2)}\n\n`;
        }
      }
      
      // Construct the system prompt with tools if available
      const fullSystemPrompt = availableTools.length > 0 
        ? `${systemPrompt}\n\n${toolsDescription}\n\nINSTRUCTIONS:
1. Analyze the user's request carefully.
2. If a tool is needed to fulfill the request, decide which tool to use.
3. Format your tool calls as JSON, wrapped in triple backticks with the 'json' tag.
4. Example tool call format:
\`\`\`json
{
  "tool_name": "tool_name_here",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  }
}
\`\`\`
5. After receiving tool results, provide a helpful response that incorporates the information.
6. If no tool is needed, respond directly to the user's request.`
        : systemPrompt;
      
      // Simulate API call to Gemini
      // In a real implementation, you would make an actual API call to Google's Gemini API
      const endpoint = '/api/gemini/chat';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model: 'gemini-1.5-pro',
          messages: [
            { role: 'system', parts: [{ text: fullSystemPrompt }] },
            ...formattedHistory,
            { role: 'user', parts: [{ text: query }] }
          ],
          generationConfig: {
            temperature: 0.2,
            maxOutputTokens: 2048
          }
        })
      });
      
      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }
      
      const data = await response.json();
      const responseText = data.candidates[0].content.parts[0].text;
      
      // Extract any tool calls from the response
      const toolCallPattern = /```json\s*(\{[^`]*\})\s*```/g;
      const toolCallMatches = [...responseText.matchAll(toolCallPattern)];
      
      const toolCalls: ToolCall[] = [];
      for (const match of toolCallMatches) {
        try {
          const toolCallJson = match[1];
          const toolCall = JSON.parse(toolCallJson);
          if (toolCall.tool_name && toolCall.parameters) {
            toolCalls.push(toolCall);
          }
        } catch (e) {
          console.error("Failed to parse tool call:", e);
        }
      }
      
      return {
        response: responseText,
        toolCalls: toolCalls.length > 0 ? toolCalls : null
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Error processing query: ${message}`);
      return {
        response: `Error: ${message}`,
        toolCalls: null
      };
    } finally {
      setIsThinking(false);
    }
  }, [systemPrompt]);

  // Process a follow-up based on tool results
  const processToolResult = useCallback(async (
    toolName: string,
    toolResult: string,
    history: ChatMessage[]
  ): Promise<string> => {
    setIsThinking(true);
    setError(null);
    
    try {
      // Format the chat history for the API
      const formattedHistory = history
        .filter(msg => msg.role !== 'system')
        .map(msg => ({
          role: msg.role,
          parts: [{ text: msg.content }]
        }));
      
      // Create a follow-up system prompt for the tool result
      const followupSystemPrompt = `The tool '${toolName}' returned the following result:

${toolResult}

Please analyze this result and provide a helpful response to the user based on this information.
Keep your response focused on the insights from the tool result.`;
      
      // Simulate API call for follow-up
      const endpoint = '/api/gemini/chat';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model: 'gemini-1.5-pro',
          messages: [
            ...formattedHistory,
            { role: 'system', parts: [{ text: followupSystemPrompt }] }
          ],
          generationConfig: {
            temperature: 0.2,
            maxOutputTokens: 2048
          }
        })
      });
      
      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }
      
      const data = await response.json();
      return data.candidates[0].content.parts[0].text;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Error processing tool result: ${message}`);
      return `Error processing tool result: ${message}`;
    } finally {
      setIsThinking(false);
    }
  }, []);

  return {
    processQuery,
    processToolResult,
    isThinking,
    error
  };
}

import { NapierConfig } from '../types/config';

const DEFAULT_CONFIG: NapierConfig = {
  mcpServers: {},
  defaults: {},
  napier: {
    model: "gemini-1.5-pro",
    api_config: { temperature: 0.2 }
  }
};

// Load configuration from public/napier_config.json
export async function loadConfig(): Promise<NapierConfig> {
  try {
    const response = await fetch('/napier_config.json');
    
    if (!response.ok) {
      console.warn(`Config file not found or invalid. Using default configuration.`);
      return DEFAULT_CONFIG;
    }
    
    const config = await response.json();
    return config as NapierConfig;
  } catch (error) {
    console.error('Error loading config:', error);
    return DEFAULT_CONFIG;
  }
}

// Get server configuration by name
export function getServerConfig(config: NapierConfig, serverName: string) {
  return config.mcpServers[serverName];
}

// Get default server name
export function getDefaultServer(config: NapierConfig) {
  return config.defaults.server;
}

// Get Napier-specific configuration
export function getNapierConfig(config: NapierConfig) {
  return config.napier;
}

// List all server configurations
export function listServers(config: NapierConfig) {
  return config.mcpServers;
}

// Function to save API keys in localStorage
export function saveApiKey(key: string, value: string) {
  localStorage.setItem(`napier_api_key_${key}`, value);
}

// Function to get API keys from localStorage
export function getApiKey(key: string): string | null {
  return localStorage.getItem(`napier_api_key_${key}`);
}

// Parse commands from user input
export function parseCommand(input: string): { 
  isCommand: boolean; 
  command: string; 
  args: string[];
} {
  const trimmedInput = input.trim();
  
  // Check if the input starts with a slash '/'
  if (!trimmedInput.startsWith('/')) {
    return { isCommand: false, command: '', args: [] };
  }
  
  // Extract the command and args
  const parts = trimmedInput.slice(1).split(' ');
  const command = parts[0].toLowerCase();
  const args = parts.slice(1).filter(arg => arg.trim() !== '');
  
  return { isCommand: true, command, args };
}

// Command help text
export const commandHelp: Record<string, string> = {
  connect: 'Connect to a configured MCP server: /connect <server_name>',
  disconnect: 'Disconnect from the current MCP server: /disconnect',
  servers: 'List all configured MCP servers: /servers',
  tools: 'List all available tools from the connected server: /tools',
  clear: 'Clear the chat history: /clear',
  help: 'Show this help message: /help',
  use: 'Use a specific tool: /use <tool_name> <parameters as JSON>'
};

// Get all available commands
export function getAvailableCommands(): string[] {
  return Object.keys(commandHelp);
}

// Get help for a specific command
export function getCommandHelp(command: string): string | undefined {
  return commandHelp[command];
}

// Get help for all commands
export function getAllCommandHelp(): string {
  let help = 'Available commands:\n\n';
  
  for (const [command, helpText] of Object.entries(commandHelp)) {
    help += `• ${helpText}\n`;
  }
  
  return help;
}

import React, { useState, useEffect, useRef } from 'react';
import { parseCommand } from '../utils/commandParser';

interface ChatInputProps {
  onSubmit: (message: string) => void;
  onCommandSubmit: (command: string, args: string[]) => void;
  isDisabled?: boolean;
  placeholder?: string;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSubmit,
  onCommandSubmit,
  isDisabled = false,
  placeholder = "Type a message or command..."
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize the textarea as content grows
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!input.trim() || isDisabled) return;
    
    const { isCommand, command, args } = parseCommand(input);
    
    if (isCommand) {
      onCommandSubmit(command, args);
    } else {
      onSubmit(input);
    }
    
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter without Shift
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form 
      onSubmit={handleSubmit} 
      className="flex items-end p-4 bg-white border-t border-gray-200 shadow-inner"
    >
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        className="flex-grow py-2 px-4 mr-2 resize-none rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        rows={1}
        style={{ maxHeight: '150px' }}
      />
      <button
        type="submit"
        disabled={!input.trim() || isDisabled}
        className={`px-4 py-2 rounded-lg bg-blue-600 text-white font-medium ${
          !input.trim() || isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700'
        }`}
      >
        Send
      </button>
    </form>
  );
};

export default ChatInput;

import React from 'react';
import { ChatMessage } from '../types/chat';
import ReactMarkdown from 'react-markdown';

interface ChatMessageProps {
  message: ChatMessage;
}

// Component for displaying chat messages with markdown support
const ChatMessageComponent: React.FC<ChatMessageProps> = ({ message }) => {
  // Format timestamp
  const formattedTime = message.timestamp.toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit' 
  });

  // Determine message style based on role
  const messageStyles = {
    user: "bg-blue-50 ml-auto",
    assistant: "bg-white",
    system: "bg-gray-100 italic text-gray-600 text-sm",
  };

  // Handle special formatting for tool results
  const isToolResult = message.isToolResult === true;
  const toolResultStyles = isToolResult 
    ? "border-l-4 border-purple-500 bg-purple-50 pl-3" 
    : "";
  
  return (
    <div className={`max-w-3xl ${message.role === 'user' ? 'ml-auto' : 'mr-auto'} mb-4`}>
      <div className="flex items-center mb-1">
        <span className="font-bold mr-2">
          {message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Napier' : 'System'}
        </span>
        {message.toolName && (
          <span className="bg-purple-100 text-purple-800 text-xs px-2 py-1 rounded-md mr-2">
            {message.toolName}
          </span>
        )}
        <span className="text-xs text-gray-500">{formattedTime}</span>
      </div>
      
      <div className={`p-3 rounded-lg ${messageStyles[message.role]} ${toolResultStyles}`}>
        <ReactMarkdown
          className="prose max-w-none"
          components={{
            pre: ({ node, ...props }) => (
              <div className="bg-gray-900 text-white p-4 rounded-md overflow-x-auto my-2">
                <pre {...props} />
              </div>
            ),
            code: ({ node, className, children, ...props }) => {
              const match = /language-(\w+)/.exec(className || '');
              return match ? (
                <code className={`bg-gray-800 px-1 text-white ${className}`} {...props}>
                  {children}
                </code>
              ) : (
                <code className="bg-gray-100 px-1 rounded" {...props}>
                  {children}
                </code>
              );
            },
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
};

export default ChatMessageComponent;

