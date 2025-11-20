# 📁 Project Structure

This document explains the organization and purpose of each file in the repository.

## Directory Layout

```
DocumentAI/
├── app/                          # Application code
│   └── Auto-Magic Document AI.py # Main Streamlit application
├── database/                     # SQL scripts
│   ├── setup_database.sql        # Database setup script
│   └── cleanup_database.sql      # Database cleanup script
├── docs/                         # Documentation
│   ├── README.md                 # Full documentation
│   ├── QUICKSTART.md             # Quick start guide
│   └── PROJECT_STRUCTURE.md      # This file
├── environment.yml               # Python environment & dependencies
├── snowflake.yml.template        # Configuration template
├── .gitignore                    # Git ignore patterns
└── README.md                     # Project overview (root)
```

## File Descriptions

### Application Files

#### `app/Auto-Magic Document AI.py`
- **Purpose**: Main Streamlit application code
- **Location**: `app/` directory
- **Contains**:
  - 4 navigation tabs (Interactive, Manage Classes, Batch Inference, History)
  - Cortex AI integration (AI_EXTRACT, PARSE_DOCUMENT, AI_COMPLETE)
  - Document classification and extraction logic
  - OCR and summarization functionality
  - Database persistence layer
- **Lines**: ~900 lines of Python
- **Dependencies**: streamlit, snowflake-snowpark-python, pandas, pypdfium2

#### `environment.yml`
- **Purpose**: Defines Python runtime and package dependencies
- **Location**: Repository root
- **Used By**: Snowflake Streamlit during deployment
- **Key Sections**:
  - Python version (3.11)
  - Anaconda packages (snowflake-snowpark-python, streamlit, pandas)
  - PyPI packages via pip (pypdfium2==4.19.0)
- **Auto-detected**: Snowflake automatically uses this file when deploying artifacts

### Configuration Files

#### `snowflake.yml.template`
- **Purpose**: Template for Snowflake Streamlit deployment configuration
- **Location**: Repository root
- **Format**: YAML (definition_version: 2)
- **Usage**: Copy to `snowflake.yml` and customize with your values
- **Key Settings**:
  - App identifier (database.schema.app_name)
  - Stage location
  - Query warehouse
  - Main file reference (`app/Auto-Magic Document AI.py`)
  - Artifacts to deploy (`app/`)
- **Used By**: `snow streamlit deploy` command
- **Note**: The actual `snowflake.yml` is not committed (see `.gitignore`)

### Database Scripts

#### `database/setup_database.sql`
- **Purpose**: Complete database initialization
- **Location**: `database/` directory
- **Creates**:
  - Database: `DOCUMENT_AI_DB`
  - Schema: `DOCS`
  - Stage: `MY_DOCS_STAGE` (with DIRECTORY enabled)
  - Tables: 5 application tables
  - Warehouse: `DOCUMENT_AI_WH`
  - Sample Data: Invoice document class
- **Execution**: Run once before deploying the app
- **Command**: `snow sql -f database/setup_database.sql --connection <conn>`

#### `database/cleanup_database.sql`
- **Purpose**: Remove all application objects
- **Location**: `database/` directory
- **Removes**:
  - Streamlit application
  - All tables and data
  - Stage and files
  - Optionally: warehouse, schema, database
- **Warning**: Destructive operation - data will be lost
- **Safety**: Requires uncommenting confirmation line

### Documentation Files

#### `README.md` (Root)
- **Purpose**: Project overview and quick navigation
- **Location**: Repository root
- **Sections**:
  - Quick overview and badges
  - Quick start commands
  - Links to detailed documentation
  - Repository structure
  - Key features and architecture
- **Length**: ~150 lines
- **Audience**: First-time visitors to the repository

#### `docs/README.md`
- **Purpose**: Comprehensive project documentation
- **Location**: `docs/` directory
- **Sections**:
  - Features and architecture
  - Prerequisites and installation
  - Configuration and deployment
  - Usage guide
  - Database schema
  - Troubleshooting
  - Performance tips
- **Length**: ~500 lines
- **Audience**: Users implementing and using the application

#### `docs/QUICKSTART.md`
- **Purpose**: Get started in 5 minutes
- **Location**: `docs/` directory
- **Sections**:
  - Step-by-step setup (4 steps)
  - Verification queries
  - Common issues
  - Next steps
- **Length**: ~200 lines
- **Audience**: Users who want to get running quickly

#### `docs/PROJECT_STRUCTURE.md`
- **Purpose**: Explain repository organization (this file)
- **Location**: `docs/` directory
- **Audience**: Contributors and maintainers

### Development Files

#### `.gitignore`
- **Purpose**: Prevent committing sensitive/temporary files
- **Excludes**:
  - Python artifacts (__pycache__, *.pyc)
  - Virtual environments (venv/, env/)
  - IDE files (.vscode/, .idea/)
  - Snowflake credentials (*.p8, *.pem, rsa_key*)
  - Snowflake configuration (snowflake.yml)
  - OS files (.DS_Store)
  - Environment files (.env*)
  - Logs and temporary files

## Database Schema

### Tables Created by setup_database.sql

```
CLASS_PROMPTS
├── class_name (PK)
├── prompts (VARIANT)
├── created_at
└── updated_at

DOCUMENTS_PROCESSED
├── file_url
├── file_ref
├── class_name (FK)
├── extraction_result (VARIANT)
└── processed_at

DOCUMENTS_EXTRACTED_FIELDS
├── file_url
├── file_ref
├── class_name
├── field_name
├── field_value (VARIANT)
├── confidence
└── extracted_at

NEW_UPLOADS
├── file_name (PK)
├── file_ref
├── stage_name
├── processed
└── uploaded_at

DOCUMENT_OCR
├── file_name (PK)
├── file_ref
├── OCR (VARIANT)
├── SUMMARY
└── processed_at
```

## Deployment Flow

```
1. Developer prepares code
   ├── app/Auto-Magic Document AI.py
   ├── environment.yml
   └── snowflake.yml (copy from snowflake.yml.template)

2. Database setup
   └── Execute database/setup_database.sql
       └── Creates DB, Schema, Tables, Stage, Warehouse

3. Snow CLI deployment (from repository root)
   └── snow streamlit deploy --replace
       └── Reads snowflake.yml configuration
       └── Reads environment.yml for dependencies
       └── Uploads app/ directory to stage
       └── Creates Streamlit app object
       └── Sets configuration

4. App execution
   └── User accesses via Snowsight
       └── Streamlit loads from stage
       └── Uses Cortex AI functions (GPU)
       └── Stores results in tables
```

## Data Flow

```
User Upload
    ↓
Streamlit UI (Auto-Magic Document AI.py)
    ↓
┌─────────────────────────────────────┐
│ Snowflake Stage (MY_DOCS_STAGE)    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Cortex AI Processing                │
│ • Classification (AI_EXTRACT)       │
│ • Field Extraction (AI_EXTRACT)     │
│ • OCR (PARSE_DOCUMENT)              │
│ • Summarization (AI_COMPLETE)       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Snowflake Tables                    │
│ • DOCUMENTS_PROCESSED               │
│ • DOCUMENTS_EXTRACTED_FIELDS        │
│ • DOCUMENT_OCR                      │
│ • NEW_UPLOADS                       │
└─────────────────────────────────────┘
    ↓
User Views Results (Streamlit UI)
```

## Maintenance

### Adding Features
1. Modify `app/Auto-Magic Document AI.py`
2. Update `environment.yml` if new packages needed
3. Redeploy: `snow streamlit deploy --replace`

### Updating Configuration
1. Edit `snowflake.yml`
2. Redeploy: `snow streamlit deploy --replace`

### Database Changes
1. Modify `database/setup_database.sql`
2. Run migration script or recreate tables
3. Note: App auto-creates tables if missing

### Documentation Updates
1. Update `docs/` files as needed
2. Keep root `README.md` in sync with `docs/README.md`
3. Update `docs/PROJECT_STRUCTURE.md` when adding files

### Version Control
- Commit all files except sensitive data
- `.gitignore` excludes credentials and temporary files
- Track changes to Python code and SQL scripts

## Best Practices

### Security
- ✅ Use private key authentication
- ✅ Keep credentials in `.gitignore`
- ✅ Use least-privilege roles
- ✅ Regular security audits

### Performance
- ✅ Right-size warehouse (SMALL → MEDIUM → LARGE)
- ✅ Enable auto-suspend on warehouse
- ✅ Use batch processing for multiple documents
- ✅ Monitor Cortex AI quota usage

### Code Quality
- ✅ Follow Python PEP 8 style guide
- ✅ Comment complex logic
- ✅ Handle exceptions gracefully
- ✅ Test changes before deployment

## Support

For questions about:
- **Files**: See this document (PROJECT_STRUCTURE.md)
- **Setup**: See `docs/QUICKSTART.md`
- **Usage**: See `docs/README.md`
- **Issues**: Check Troubleshooting section in `docs/README.md`
- **Overview**: See root `README.md`

---

**Last Updated**: 2025-01-21

