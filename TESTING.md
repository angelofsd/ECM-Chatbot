# Quick Testing Guide for ECM RAG Chatbot

## Prerequisites

1. **Docker & Services Running**
   ```bash
   # Start Postgres + Qdrant
   docker-compose up -d
   
   # Verify they're running
   docker-compose ps
   ```

2. **Backend Server Running**
   ```bash
   # In terminal 1: Start FastAPI
   cd C:/Users/angela/dev/ECM-Chatbot
   python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Frontend Server Running**
   ```bash
   # In terminal 2: Start Next.js dev server
   cd C:/Users/angela/dev/ECM-Chatbot/ui
   npm run dev
   ```

## Testing the System

### 1. Backend Health Check

```bash
# Check if backend is running
curl http://localhost:8000/health

# Expected response:
# {"status":"ok"}
```

### 2. Query a Question

```bash
# Test the /query endpoint
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the timeline for ECM replacement?","top_k":5}'

# Expected response includes:
# {
#   "query": "What is the timeline for ECM replacement?",
#   "answer": "...",
#   "citations": [...],
#   "tokens_used": 1234,
#   "sources_count": 5,
#   "model": "gpt-5-mini"
# }
```

### 3. Frontend Access

Open browser to: **http://localhost:3000**

- Type a question in the input field
- Press Enter to send
- Watch for response with citations
- Click "Sources" to expand citation list

## Troubleshooting

### Backend Connection Issues

```bash
# Check if backend is listening
netstat -an | findstr :8000

# Check if Docker containers are running
docker ps

# View backend logs
docker-compose logs -f api
```

### Frontend Issues

```bash
# Check if Next.js is running
netstat -an | findstr :3000

# Check browser console for errors (F12 → Console tab)
```

### API Key Issues

```bash
# Verify OpenAI API key is set
echo $env:OPENAI_API_KEY

# If not set, create .env file in project root:
# OPENAI_API_KEY=sk-...
# POSTGRES_URL=postgresql://user:pass@localhost:15432/ecm_rag
# QDRANT_URL=http://localhost:6333
```

## End-to-End Test Scenario

1. **Start all services** (Docker, backend, frontend)
2. **Open** http://localhost:3000 in browser
3. **Type query**: "What are the ECM replacement requirements?"
4. **Verify response**:
   - ✅ Answer appears in chat
   - ✅ "Sources" section shows citations
   - ✅ No errors in console (F12)
5. **Check backend logs**:
   - Should see POST /query requests
   - No 500 errors
   - OpenAI API calls logged

## Performance Metrics to Check

| Metric | Expected | Command |
|--------|----------|---------|
| First response time | < 5 seconds | Time from send to answer |
| Document count | 252 | `SELECT COUNT(*) FROM documents;` |
| Chunk count | 1,471 | `SELECT COUNT(*) FROM chunks;` |
| Qdrant vectors | 1,471 | GET http://localhost:6333/collections/ecm_docs/points/count |

## Example Queries to Test

- "What is the timeline for ECM replacement?"
- "What vendors were evaluated?"
- "What are the requirements for ECM?"
- "What is P&P compliance related to ECM?"
- "What emails discuss budget?"

## Common Error Messages

### "Cannot connect to backend at http://localhost:8000"
- Start backend: `python -m uvicorn api.main:app --reload`
- Check port: `netstat -an | findstr :8000`

### "No documents found for query"
- Verify documents were ingested: `SELECT COUNT(*) FROM documents;`
- Check Qdrant: `GET http://localhost:6333/collections/ecm_docs/points/count`

### "OpenAI API error"
- Verify API key: `echo $env:OPENAI_API_KEY`
- Check quota at: https://platform.openai.com/account/usage/overview
- Model availability: gpt-5-mini should be available

### "Database connection refused"
- Start Docker: `docker-compose up -d`
- Verify Postgres: `docker ps | grep postgres`
- Check port: `netstat -an | findstr :15432`

## Next Steps After Testing

- [ ] Deploy frontend to Vercel or similar
- [ ] Set up production database backup strategy
- [ ] Add user authentication (Azure AD)
- [ ] Implement query logging and analytics
- [ ] Create user feedback system
- [ ] Build admin dashboard for document management

---

**Testing Date**: October 29, 2025
**Status**: Ready for end-to-end testing
