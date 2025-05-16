const express = require('express');
const { createServer } = require('http');
const { spawn } = require('child_process');
const { MCP, initServer } = require('@playwright/mcp');

const app = express();
const server = createServer(app);

// Create an MCP server
const mcp = new MCP();

// Initialize the MCP server and register tools
initServer({
  mcp,
  tools: [
    // Register Playwright tools
    {
      name: 'browser.navigate',
      description: 'Navigate to a URL in the browser',
      inputSchema: {
        type: 'object',
        properties: {
          url: {
            type: 'string',
            description: 'The URL to navigate to'
          }
        },
        required: ['url']
      },
      handler: async ({ url }) => {
        const browser = await mcp.playwright.chromium.launch();
        const page = await browser.newPage();
        await page.goto(url);
        const title = await page.title();
        await browser.close();
        return { content: `Navigated to ${url}. Page title: ${title}` };
      }
    },
    {
      name: 'browser.screenshot',
      description: 'Take a screenshot of a web page',
      inputSchema: {
        type: 'object',
        properties: {
          url: {
            type: 'string',
            description: 'The URL to take a screenshot of'
          }
        },
        required: ['url']
      },
      handler: async ({ url }) => {
        const browser = await mcp.playwright.chromium.launch();
        const page = await browser.newPage();
        await page.goto(url);
        const screenshot = await page.screenshot({ encoding: 'base64' });
        await browser.close();
        return { content: `Screenshot taken of ${url}. Base64 data: ${screenshot.substring(0, 50)}...` };
      }
    },
    {
      name: 'browser.getContent',
      description: 'Get the HTML content of a web page',
      inputSchema: {
        type: 'object',
        properties: {
          url: {
            type: 'string',
            description: 'The URL to get content from'
          },
          selector: {
            type: 'string',
            description: 'Optional CSS selector to get specific content',
            default: 'body'
          }
        },
        required: ['url']
      },
      handler: async ({ url, selector = 'body' }) => {
        const browser = await mcp.playwright.chromium.launch();
        const page = await browser.newPage();
        await page.goto(url);
        const content = await page.$eval(selector, (el) => el.innerHTML);
        await browser.close();
        return { content: content.substring(0, 5000) }; // Limit content size
      }
    },
    {
      name: 'browser.click',
      description: 'Click on an element on a web page',
      inputSchema: {
        type: 'object',
        properties: {
          url: {
            type: 'string',
            description: 'The URL of the page'
          },
          selector: {
            type: 'string',
            description: 'CSS selector for the element to click'
          }
        },
        required: ['url', 'selector']
      },
      handler: async ({ url, selector }) => {
        const browser = await mcp.playwright.chromium.launch();
        const page = await browser.newPage();
        await page.goto(url);
        await page.click(selector);
        const title = await page.title();
        await browser.close();
        return { content: `Clicked on element "${selector}" on page "${url}". New page title: ${title}` };
      }
    }
  ]
});

// Start the server
const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  console.log(`MCP Playwright server running on port ${PORT}`);
});

// Handle shutdown gracefully
process.on('SIGINT', () => {
  console.log('Shutting down MCP Playwright server');
  server.close(() => {
    process.exit(0);
  });
});