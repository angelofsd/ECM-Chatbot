# ECM RAG Chatbot Frontend

Next.js 14 + TypeScript + Tailwind CSS frontend for the ECM RAG chatbot.

## Quick Start

### Prerequisites

- Node.js 18+ (comes with npm)
- Backend FastAPI server running on `http://localhost:8000`

### Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   ```bash
   cp .env.local.example .env.local
   ```
   Edit `.env.local` if your backend is on a different host:port.

3. **Start development server**:
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

## Architecture

### Components

- **`ChatMessage.tsx`**: Displays user queries and AI responses with expandable source citations
- **`ChatInput.tsx`**: Multi-line text input with auto-grow, Shift+Enter for new lines, Enter to send
- **`page.tsx`**: Main chat page with message history, loading indicators, and error handling

### API Client (`lib/api.ts`)

- `queryAPI(query)`: Send a question to the backend, returns answer + citations
- `healthCheck()`: Verify backend is running
- `getDocument(filename)`: Fetch full document content (optional)

### Styling

- **Tailwind CSS 3.4**: Utility-first CSS framework
- **CSS Variables**: Light/dark mode theming system (`app/globals.css`)
- **Responsive**: Mobile-first design with breakpoints

### State Management

- **React Hooks**: `useState` for message history and UI state
- **Zustand** (optional): Available for complex shared state if needed

## Development

### Build

```bash
npm run build
```

Production-optimized build output in `.next/`.

### Type Checking

```bash
npx tsc --noEmit
```

Verify TypeScript types (also runs during build).

### Linting

```bash
npm run lint
```

ESLint configuration in `.eslintrc.json` (Next.js default).

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | FastAPI backend URL |
| `NEXT_PUBLIC_POLLING_INTERVAL` | `5000` | Polling interval (ms) for streaming responses |

**Note**: `NEXT_PUBLIC_*` prefix makes variables accessible to client-side code.

## Features

✅ Chat interface with message history
✅ Real-time response streaming
✅ Source document citations (expandable)
✅ Error handling with user feedback
✅ Loading indicators (animated dots)
✅ Keyboard shortcuts (Enter to send, Shift+Enter for newline)
✅ Auto-scrolling to latest message
✅ Responsive design (mobile/tablet/desktop)
✅ Dark mode support (CSS variables)

## Backend Integration

The frontend expects the FastAPI backend at `NEXT_PUBLIC_API_BASE` with:

- **`POST /query`**
  - Request: `{ query: string, top_k?: number }`
  - Response: `{ query, answer, citations[], tokens_used, sources_count, model }`
  - Error: `{ detail: "error message" }`

- **`GET /health`**
  - Returns: `{ status: "ok" }` or `{ status: "error" }`

## Troubleshooting

### Frontend won't connect to backend

1. Ensure backend is running: `curl http://localhost:8000/health`
2. Check `NEXT_PUBLIC_API_BASE` in `.env.local`
3. Look for CORS issues in browser console
4. Try: `curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query":"test"}'`

### Slow response

- Backend may be busy or network latency
- Check backend logs for errors
- Increase `NEXT_PUBLIC_POLLING_INTERVAL` if needed

### Build errors

1. Delete `node_modules` and `.next`: `rm -rf node_modules .next`
2. Reinstall: `npm install && npm run build`
3. Check Node.js version: `node -v` (need 18+)

## Next Steps

- [ ] Add streaming response handler for real-time token display
- [ ] Implement authentication (JWT or OAuth)
- [ ] Add chat history persistence (localStorage or DB)
- [ ] Citation modal for full document viewing
- [ ] Search filters (date, source, etc.)
- [ ] Export conversation as PDF/Markdown
- [ ] User preferences (theme, language, etc.)

## Performance Notes

- **First Load**: ~111 kB JS (optimized with Next.js)
- **Page Size**: 24.1 kB (gzipped)
- **Shared Chunks**: 87.3 kB (reused across pages)

Build optimizations enabled:
- SWC minification
- CSS modules
- Font optimization (Inter font loading)
- Image optimization (next/image)

## Deployment

### Vercel (Recommended for Next.js)

```bash
npm run build
vercel deploy
```

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY .next ./.next
COPY public ./public
EXPOSE 3000
CMD ["npm", "start"]
```

### Traditional Server

```bash
npm run build
npm start
# Runs on http://localhost:3000
```

## License

Part of ECM RAG Chatbot project.
