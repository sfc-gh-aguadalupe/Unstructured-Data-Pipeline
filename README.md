# 🤖 Snowflake Document AI - Intelligent Document Processing

An intelligent document processing pipeline built on **Snowflake Cortex AI** that automatically classifies documents, extracts structured data, performs OCR, and generates summaries—all using native Snowflake capabilities.

![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)

## ✨ Key Features

- **🔍 Automatic Classification**: AI determines document type (invoice, receipt, contract, etc.)
- **📊 Smart Field Extraction**: Extracts structured data based on document class
- **📝 OCR Processing**: Full text extraction using Snowflake's PARSE_DOCUMENT
- **🤖 AI Summarization**: Generates concise summaries of document content
- **⚡ Batch Processing**: Process multiple documents in parallel
- **🎯 Custom Classes**: Define your own document types and extraction prompts

## 🚀 Quick Start

### Prerequisites
- Snowflake account with Cortex AI enabled
- Snowflake CLI installed
- Role with database creation privileges

### Installation (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/sfc-gh-aguadalupe/Unstructured-Data-Pipeline.git
cd Unstructured-Data-Pipeline

# 2. Configure Snowflake connection
snow connection add

# 3. Set up database
snow sql -f database/setup_database.sql

# 4. Configure deployment (copy template and customize)
cp snowflake.yml.template snowflake.yml
# Edit snowflake.yml with your database/schema/warehouse names

# 5. Deploy the app
snow streamlit deploy --replace

# 6. Open in browser
snow streamlit get-url DOCUMENT_AI_APP
```

## 📚 Documentation

- **[📖 Full Documentation](docs/README.md)** - Complete guide with architecture, features, and troubleshooting
- **[🚀 Quick Start Guide](docs/QUICKSTART.md)** - Get running in 5 minutes
- **[📁 Project Structure](docs/PROJECT_STRUCTURE.md)** - Repository organization and file descriptions

## 🏗️ Architecture

```
Streamlit UI (Python)
        ↓
Snowflake Cortex AI (GPU)
├── AI_EXTRACT (Classification & Extraction)
├── PARSE_DOCUMENT (OCR)
└── AI_COMPLETE (Summarization)
        ↓
Snowflake Storage (Stages & Tables)
```

**All processing happens natively in Snowflake** - no external services or APIs required!

## 📊 Processing Modes

1. **Interactive Mode**: Upload and process documents one at a time
2. **Batch Processing**: Process multiple documents in parallel with real-time progress
3. **SQL Mode**: Process entire stage contents in a single SQL query

## 🗄️ What Gets Created

### Database Objects
- Database: `DOCUMENT_AI_DB`
- Schema: `DOCS`
- Stage: `MY_DOCS_STAGE` (for document storage)
- Warehouse: `DOCUMENT_AI_WH`

### Tables
- `CLASS_PROMPTS` - Document class definitions
- `DOCUMENTS_PROCESSED` - Processing results
- `DOCUMENTS_EXTRACTED_FIELDS` - Extracted data fields
- `NEW_UPLOADS` - Upload tracking
- `DOCUMENT_OCR` - OCR results and summaries

## 🎯 Use Cases

- **Invoice Processing**: Extract vendor, amount, date, line items
- **Receipt Management**: Capture merchant, total, items, payment method
- **Contract Analysis**: Extract parties, dates, terms, obligations
- **Form Processing**: Parse applications, surveys, questionnaires
- **Healthcare Documents**: Extract patient info, diagnoses, prescriptions
- **Legal Documents**: Analyze agreements, filings, correspondence

## 🔧 Requirements

### Snowflake Account
- Cortex AI enabled (contact Snowflake if needed)
- Streamlit in Snowflake
- Supported region with Cortex AI availability

### Python Environment (for deployment only)
- Python 3.11
- Snowflake CLI (`pip install snowflake-cli-labs`)

**Note**: The app runs entirely in Snowflake. Python is only needed for deployment via Snowflake CLI.

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs or request features via Issues
- Submit pull requests with improvements
- Share your use cases and feedback

## 📄 License

This project is provided as-is for demonstration and educational purposes.

## 🙏 Acknowledgments

- Built with [Snowflake Cortex AI](https://docs.snowflake.com/en/user-guide/snowflake-cortex)
- Powered by [Streamlit in Snowflake](https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit)
- Uses [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) for PDF rendering

## 📞 Support

- 📖 [Snowflake Documentation](https://docs.snowflake.com)
- 💬 [Snowflake Community](https://community.snowflake.com)
- 🐛 [Report Issues](https://github.com/sfc-gh-aguadalupe/Unstructured-Data-Pipeline/issues)

---

**Ready to get started?** Follow the [Quick Start Guide](docs/QUICKSTART.md) →

