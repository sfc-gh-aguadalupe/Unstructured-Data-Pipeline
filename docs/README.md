# 🤖 Snowflake Document AI - Intelligent Document Processing

An intelligent document processing application built on **Snowflake Cortex AI** that automatically classifies documents, extracts structured data, performs OCR, and generates summaries—all using native Snowflake capabilities.

![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Usage](#usage)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## ✨ Features

### 🔍 Intelligent Processing
- **Automatic Classification**: AI automatically determines document type (invoice, receipt, contract, etc.)
- **Smart Field Extraction**: Extracts structured data based on document class
- **OCR Processing**: Full text extraction using Snowflake's PARSE_DOCUMENT
- **AI Summarization**: Generates concise summaries of document content

### 📊 Multiple Processing Modes
- **Interactive Mode**: Upload and process documents one at a time with live preview
- **Batch Processing**: Process multiple documents in parallel
- **Single SQL Mode**: Process entire stage contents in one SQL query

### 🎯 Class Management
- Define custom document classes with field extraction prompts
- Auto-generate extraction prompts using AI
- Edit and manage extraction schemas via intuitive UI

### 📈 History & Analytics
- View all processed documents with filtering
- Export results as CSV or JSON
- Track extraction fields across document types

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI (Python)                    │
│  • File Upload  • Preview  • Batch Processing  • History    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Snowflake Cortex AI                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ AI_EXTRACT   │  │PARSE_DOCUMENT│  │ AI_COMPLETE  │     │
│  │ (GPU)        │  │   (GPU)      │  │   (GPU)      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               Snowflake Data Storage                        │
│  • Stages (Documents)  • Tables (Results)  • Warehouses    │
└─────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Streamlit in Snowflake**: Native Streamlit app running inside Snowflake
- **Cortex AI Functions**: GPU-accelerated AI models for document understanding
- **Snowpark Python**: Direct integration with Snowflake data and compute
- **Stages**: Store uploaded PDFs and images
- **Tables**: Persist classification, extraction, and OCR results

## 📋 Prerequisites

### Snowflake Account Requirements

1. **Snowflake Account** with access to:
   - ✅ Snowflake Cortex AI (contact Snowflake if not enabled)
   - ✅ Streamlit in Snowflake
   - ✅ Supported region with Cortex AI availability

2. **Privileges Required**:
   ```sql
   -- Database and schema permissions
   GRANT CREATE DATABASE ON ACCOUNT TO ROLE <your_role>;
   GRANT CREATE SCHEMA ON DATABASE <database> TO ROLE <your_role>;
   
   -- Table and stage permissions
   GRANT CREATE TABLE ON SCHEMA <schema> TO ROLE <your_role>;
   GRANT CREATE STAGE ON SCHEMA <schema> TO ROLE <your_role>;
   
   -- Warehouse permissions
   GRANT CREATE WAREHOUSE ON ACCOUNT TO ROLE <your_role>;
   ```

3. **Cortex AI Access**:
   ```sql
   -- Verify Cortex AI access
   SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-7b', 'Hello');
   ```

### Local Development Requirements

- **Python 3.9+** (for local testing)
- **Snowflake CLI** (for deployment)
- **Snowflake Account** with credentials

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd DocumentAI
```

### 2. Install Snowflake CLI (if not installed)

```bash
# macOS
brew install snowflake-cli

# Or using pip
pip install snowflake-cli-labs
```

### 3. Configure Snowflake Connection

```bash
snow connection add

# Or edit ~/.snowflake/config.toml manually
```

For private key authentication (recommended):
```toml
[connections.keypair-auth]
account = "your-account"
user = "your-username"
authenticator = "SNOWFLAKE_JWT"
private_key_file = "/path/to/rsa_key.p8"
warehouse = "COMPUTE_WH"
role = "ACCOUNTADMIN"
```

## ⚙️ Configuration

### Update `snowflake.yml`

Edit the deployment configuration to match your Snowflake environment:

```yaml
definition_version: 2

entities:
  DOCUMENT_AI_APP:
    type: streamlit
    identifier: DOCUMENT_AI_DB.DOCS.DOCUMENT_AI_APP
    stage: DOCUMENT_AI_DB.DOCS.MY_DOCS_STAGE
    query_warehouse: COMPUTE_WH
    main_file: Auto-Magic Document AI.py
    title: "Snowflake Document AI"
```

**Key Configuration Options:**
- `identifier`: Fully qualified app name (database.schema.app_name)
- `stage`: Stage where app files and documents are stored
- `query_warehouse`: Warehouse used to run the app
- `main_file`: Python file containing the Streamlit app

### Python Environment

The `environment.yml` defines package dependencies:

```yaml
name: document_ai_env
channels:
  - snowflake
dependencies:
  - python=3.11
  - snowflake-snowpark-python
  - streamlit
  - pandas
  - pip:
    - pypdfium2==4.19.0  # PyPI package for PDF preview
```

## 🎯 Deployment

### Step 1: Set Up Database Objects

Run the SQL setup script to create required database objects:

```bash
# Execute via Snowflake CLI
snow sql -f setup_database.sql --connection keypair-auth

# Or execute in Snowsight
```

This creates:
- ✅ Database: `DOCUMENT_AI_DB`
- ✅ Schema: `DOCS`
- ✅ Stage: `MY_DOCS_STAGE`
- ✅ 5 Tables: `CLASS_PROMPTS`, `DOCUMENTS_PROCESSED`, `DOCUMENTS_EXTRACTED_FIELDS`, `NEW_UPLOADS`, `DOCUMENT_OCR`
- ✅ Warehouse: `DOCUMENT_AI_WH`
- ✅ Sample data: Invoice document class

### Step 2: Deploy the Streamlit App

```bash
# Deploy using Snowflake CLI
snow streamlit deploy --replace --connection keypair-auth

# Output:
# ✓ Creating stage
# ✓ Deploying files
# ✓ Creating Streamlit app
# URL: https://app.snowflake.com/.../streamlit-apps/...
```

### Step 3: Open the Application

```bash
# Open in browser
snow streamlit open DOCUMENT_AI_APP --connection keypair-auth

# Or get the URL
snow streamlit get-url DOCUMENT_AI_APP --connection keypair-auth
```

## 📖 Usage

### Interactive Mode

1. **Upload a Document**
   - Click "Browse files" in the sidebar
   - Select a PDF or image file
   - Preview appears automatically

2. **Processing**
   - App automatically classifies the document
   - Generates or uses existing extraction prompts
   - Extracts structured data
   - Performs OCR and generates summary
   - Stores all results in Snowflake tables

3. **View Results**
   - **Progress Tab**: See real-time processing status
   - **Raw JSON Tab**: View complete extraction response
   - **Properties Tab**: See extracted fields in card format
   - **OCR Tab**: View full text extraction and summary

### Manage Classes

1. Navigate to **Manage Classes**
2. Create or edit document classes
3. Define extraction prompts as JSON:
   ```json
   {
     "invoice_number": "What is the invoice number?",
     "total_amount": "What is the total amount?",
     "vendor_name": "Who is the vendor?"
   }
   ```
4. Save to persist in `CLASS_PROMPTS` table

### Batch Processing

1. Navigate to **Batch Inference**
2. Select a stage containing documents
3. Choose a document class
4. Run in **Stream Mode** (parallel) or **SQL Mode** (single query)
5. Results display in real-time table
6. Download as CSV or JSON

### History

1. Navigate to **History**
2. Filter by:
   - Document class
   - Stage name
   - Filename
3. View summaries by class or document
4. Export filtered results

## 🗄️ Database Schema

### Table: CLASS_PROMPTS
```sql
class_name STRING PRIMARY KEY      -- Document class identifier
prompts VARIANT                     -- Extraction prompt definitions (JSON)
```

### Table: DOCUMENTS_PROCESSED
```sql
file_url STRING                     -- Full stage path (@stage/file.pdf)
file_ref STRING                     -- Relative filename
class_name STRING                   -- Document classification
extraction_result VARIANT           -- Complete AI extraction result
```

### Table: DOCUMENTS_EXTRACTED_FIELDS
```sql
file_url STRING                     -- Full stage path
file_ref STRING                     -- Relative filename
class_name STRING                   -- Document classification
field_name STRING                   -- Extracted field name
field_value VARIANT                 -- Extracted field value
confidence FLOAT                    -- Confidence score (currently null)
```

### Table: NEW_UPLOADS
```sql
file_name STRING PRIMARY KEY        -- Unique filename
file_ref STRING                     -- Full reference path
stage_name STRING                   -- Stage location
processed BOOLEAN                   -- Processing status
```

### Table: DOCUMENT_OCR
```sql
file_name STRING PRIMARY KEY        -- Unique filename
file_ref STRING                     -- Full reference path
OCR VARIANT                         -- Full OCR extraction
SUMMARY VARCHAR                     -- AI-generated summary
```

## 🔧 Troubleshooting

### Package Conflicts

**Error**: `Cannot create a Python function with the specified packages`

**Solution**: Ensure `environment.yml` uses Python 3.11 or 3.12 and includes pip section:
```yaml
dependencies:
  - python=3.11
  - pip:
    - pypdfium2==4.19.0
```

### Cortex AI Not Available

**Error**: `AI_EXTRACT function not found`

**Solution**: 
1. Verify Cortex AI is enabled: Contact Snowflake support
2. Check region support: Cortex AI is not available in all regions
3. Verify permissions: Ensure role can execute system functions

### Stage Directory Not Enabled

**Error**: `Directory is not enabled on stage`

**Solution**: Recreate stage with DIRECTORY enabled:
```sql
CREATE OR REPLACE STAGE MY_DOCS_STAGE
  DIRECTORY = (ENABLE = TRUE);
```

### No Current Database

**Error**: `This session does not have a current database`

**Solution**: Update `snowflake.yml` with fully qualified identifiers:
```yaml
identifier: DATABASE.SCHEMA.APP_NAME
stage: DATABASE.SCHEMA.STAGE_NAME
```

### MFA Issues

**Solution**: Use private key authentication instead of password + MFA:
```bash
# Generate key pair
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub

# Add public key to Snowflake user
ALTER USER <username> SET RSA_PUBLIC_KEY='<public_key_value>';

# Update connection to use private key
```

## 📊 Performance Considerations

### Warehouse Sizing
- **SMALL**: Single-user interactive use
- **MEDIUM**: Multi-user or moderate batch processing (recommended)
- **LARGE**: Heavy batch processing with large documents

### GPU Compute
- Cortex AI functions automatically use GPU
- No need for GPU warehouses
- All AI inference runs on Snowflake's managed GPU infrastructure

### Caching
- Anaconda packages are cached on warehouse
- First run after warehouse resume may be slower (~30 seconds)
- Keep warehouses running during active processing

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is provided as-is for demonstration and educational purposes.

## 🙏 Acknowledgments

- Built with [Snowflake Cortex AI](https://docs.snowflake.com/en/user-guide/snowflake-cortex)
- Powered by [Streamlit in Snowflake](https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit)
- Uses [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) for PDF rendering

---

**Need Help?** 
- 📖 [Snowflake Documentation](https://docs.snowflake.com)
- 💬 [Snowflake Community](https://community.snowflake.com)
- 🐛 [Report Issues](your-repo-issues-url)

