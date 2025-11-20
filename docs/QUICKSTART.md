# 🚀 Quick Start Guide

Get up and running with Snowflake Document AI in 5 minutes!

## Prerequisites Checklist

- [ ] Snowflake account with Cortex AI enabled
- [ ] Snowflake CLI installed (`snow --version`)
- [ ] Snowflake connection configured with private key auth
- [ ] Role with CREATE DATABASE and CREATE WAREHOUSE privileges

## Step-by-Step Setup

### 1. Configure Snowflake Connection (2 min)

```bash
# Test existing connection
snow connection test

# Or add new connection
snow connection add
```

For private key auth, you'll need:
- Account identifier (e.g., `SFSEEUROPE-USWEST2DEMO`)
- Username
- Private key file path
- Warehouse name
- Role (recommend `ACCOUNTADMIN` for setup)

### 2. Set Up Database (1 min)

```bash
# Execute the setup script
snow sql -f database/setup_database.sql --connection your-connection-name
```

This creates:
- ✅ `DOCUMENT_AI_DB` database
- ✅ `DOCS` schema
- ✅ `MY_DOCS_STAGE` stage
- ✅ 5 application tables
- ✅ `DOCUMENT_AI_WH` warehouse

### 3. Deploy the App (1 min)

```bash
# Deploy using Snow CLI
snow streamlit deploy --replace --connection your-connection-name
```

Expected output:
```
Creating DOCUMENT_AI_DB.DOCS.MY_DOCS_STAGE stage
Deploying files...
Creating DOCUMENT_AI_DB.DOCS.DOCUMENT_AI_APP Streamlit
✓ Streamlit successfully deployed
```

### 4. Open and Use (1 min)

```bash
# Open app in browser
snow streamlit open DOCUMENT_AI_APP --connection your-connection-name
```

**First Use:**
1. Upload a PDF or image (invoice, receipt, etc.)
2. Wait ~30 seconds for processing
3. View extracted data in tabs:
   - Progress: Real-time status
   - Properties: Extracted fields
   - OCR: Full text extraction
   - Raw JSON: Complete response

## Verify Installation

Run these SQL queries to verify setup:

```sql
-- Check database and tables
USE DATABASE DOCUMENT_AI_DB;
USE SCHEMA DOCS;

SHOW TABLES;
-- Should show: CLASS_PROMPTS, DOCUMENTS_PROCESSED, 
--              DOCUMENTS_EXTRACTED_FIELDS, NEW_UPLOADS, DOCUMENT_OCR

-- Check stage
LIST @MY_DOCS_STAGE;

-- Verify Cortex AI access
SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-7b', 'test') AS test;
```

## Common Issues

### Issue: Package conflicts
```
Error: Cannot create a Python function with the specified packages
```
**Solution**: `environment.yml` should have Python 3.11 with pip section for pypdfium2

### Issue: No current database
```
Error: This session does not have a current database
```
**Solution**: Update `snowflake.yml` with fully qualified names:
```yaml
identifier: DOCUMENT_AI_DB.DOCS.DOCUMENT_AI_APP
stage: DOCUMENT_AI_DB.DOCS.MY_DOCS_STAGE
```

### Issue: Cortex AI not found
```
Error: AI_EXTRACT function not found
```
**Solution**: Contact Snowflake support to enable Cortex AI on your account

## Next Steps

### Process Your First Document
1. Open the app in your browser
2. Navigate to "Interactive" tab (default)
3. Upload a PDF invoice or receipt
4. Review extracted data

### Create Custom Classes
1. Navigate to "Manage Classes"
2. Click "Create new"
3. Enter class name (e.g., "purchase_order")
4. Define extraction prompts:
   ```json
   {
     "po_number": "What is the purchase order number?",
     "vendor": "Who is the vendor?",
     "total": "What is the total amount?"
   }
   ```
5. Click "Save"

### Batch Processing
1. Upload multiple documents to your stage:
   ```sql
   PUT file:///path/to/invoices/*.pdf @MY_DOCS_STAGE;
   ```
2. Navigate to "Batch Inference" tab
3. Select stage and document class
4. Click "Run (stream)" for parallel processing
5. Download results as CSV or JSON

## Resource Configuration

### For Development/Testing
```sql
ALTER WAREHOUSE DOCUMENT_AI_WH SET WAREHOUSE_SIZE = 'SMALL';
```

### For Production/Multi-user
```sql
ALTER WAREHOUSE DOCUMENT_AI_WH SET WAREHOUSE_SIZE = 'MEDIUM';
```

### For Heavy Batch Processing
```sql
ALTER WAREHOUSE DOCUMENT_AI_WH SET WAREHOUSE_SIZE = 'LARGE';
```

## Getting Help

- 📖 [Full Documentation](README.md)
- 📁 [Project Structure](PROJECT_STRUCTURE.md)
- 📚 [Snowflake Cortex Docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex)
- 💬 [Snowflake Community](https://community.snowflake.com)

---

**Success!** 🎉 You now have an intelligent document processing pipeline running in Snowflake!

