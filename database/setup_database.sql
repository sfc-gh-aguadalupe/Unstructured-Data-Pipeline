-- ============================================================================
-- Snowflake Document AI - Database Setup
-- ============================================================================
-- This script sets up all required database objects for the Document AI app
-- Run this script before deploying the Streamlit application
-- ============================================================================

-- Step 1: Create Database and Schema
-- ============================================================================
CREATE DATABASE IF NOT EXISTS DOCUMENT_AI_DB
  COMMENT = 'Database for Document AI application using Snowflake Cortex';

USE DATABASE DOCUMENT_AI_DB;

CREATE SCHEMA IF NOT EXISTS DOCS
  COMMENT = 'Schema for Document AI tables and stages';

USE SCHEMA DOCUMENT_AI_DB.DOCS;

-- Step 2: Create Stages
-- ============================================================================

-- Stage for Document Storage (used by end-users and Cortex AI)
-- IMPORTANT: Must use server-side encryption (SNOWFLAKE_SSE) for Cortex AI compatibility
-- Client-side encryption blocks AI_EXTRACT and other Cortex AI functions
CREATE OR REPLACE STAGE MY_DOCS_STAGE
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')  -- Server-side encryption only
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'Stage for storing PDF and image documents - Cortex AI compatible';

-- Stage for Streamlit App Deployment (stores application code)
-- Using server-side encryption for consistency
CREATE OR REPLACE STAGE STREAMLIT_APP_STAGE
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
  COMMENT = 'Stage for Streamlit application code and environment files';

-- Verify stage creation
SHOW STAGES;

-- Step 3: Create Application Tables
-- ============================================================================
-- These tables are auto-created by the app, but you can create them manually
-- for better control over structure and permissions

-- Table 1: Document Classes and Extraction Prompts
CREATE TABLE IF NOT EXISTS CLASS_PROMPTS (
  class_name STRING PRIMARY KEY COMMENT 'Unique document class name (e.g., invoice, receipt)',
  prompts VARIANT COMMENT 'JSON object defining field extraction prompts',
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Stores document classification types and their extraction prompt definitions';

-- Table 2: Processed Documents (Master Record)
CREATE TABLE IF NOT EXISTS DOCUMENTS_PROCESSED (
  file_url STRING COMMENT 'Full stage path to the document file',
  file_ref STRING COMMENT 'Relative file path or name',
  class_name STRING COMMENT 'Classified document type',
  extraction_result VARIANT COMMENT 'Complete extraction result in JSON format',
  processed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT fk_class FOREIGN KEY (class_name) REFERENCES CLASS_PROMPTS(class_name)
) COMMENT = 'Master table of all processed documents with full extraction results';

-- Table 3: Extracted Fields (Normalized View)
CREATE TABLE IF NOT EXISTS DOCUMENTS_EXTRACTED_FIELDS (
  file_url STRING COMMENT 'Full stage path to the document file',
  file_ref STRING COMMENT 'Relative file path or name',
  class_name STRING COMMENT 'Document class',
  field_name STRING COMMENT 'Name of the extracted field',
  field_value VARIANT COMMENT 'Value of the extracted field (can be any JSON type)',
  confidence FLOAT COMMENT 'Confidence score (0-1) - currently not populated',
  extracted_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Normalized table with individual extracted fields from documents';

-- Table 4: Upload Tracking
CREATE TABLE IF NOT EXISTS NEW_UPLOADS (
  file_name STRING PRIMARY KEY COMMENT 'Unique filename',
  file_ref STRING COMMENT 'Full reference path including stage',
  stage_name STRING COMMENT 'Stage where file is located',
  processed BOOLEAN DEFAULT FALSE COMMENT 'Whether document has been processed',
  uploaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Tracks uploaded files and their processing status';

-- Table 5: OCR and Summary Results
CREATE TABLE IF NOT EXISTS DOCUMENT_OCR (
  file_name STRING PRIMARY KEY COMMENT 'Unique filename',
  file_ref STRING COMMENT 'Full reference path including stage',
  OCR VARIANT COMMENT 'Full OCR text extraction result',
  SUMMARY VARCHAR COMMENT 'AI-generated summary of document content',
  processed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Stores OCR text extraction and AI summaries for documents';

-- Step 4: Performance Optimization
-- ============================================================================
-- Note: Snowflake doesn't support traditional indexes on standard tables
-- Performance is automatically optimized through:
-- - Micro-partitioning
-- - Clustering keys (can be added if needed)
-- - Automatic query optimization

-- Step 5: Create Warehouse for the Application
-- ============================================================================
-- Standard warehouse is sufficient since Cortex AI handles GPU compute

CREATE WAREHOUSE IF NOT EXISTS DOCUMENT_AI_WH
  WITH 
    WAREHOUSE_SIZE = 'MEDIUM'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Warehouse for Document AI Streamlit application';

-- Step 6: Grant Permissions
-- ============================================================================
-- Grant necessary permissions to your role (modify as needed)

-- Replace 'YOUR_ROLE' with your actual role name
SET my_role = CURRENT_ROLE();

GRANT USAGE ON DATABASE DOCUMENT_AI_DB TO ROLE IDENTIFIER($my_role);
GRANT USAGE ON SCHEMA DOCUMENT_AI_DB.DOCS TO ROLE IDENTIFIER($my_role);
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA DOCUMENT_AI_DB.DOCS TO ROLE IDENTIFIER($my_role);
GRANT ALL PRIVILEGES ON STAGE DOCUMENT_AI_DB.DOCS.MY_DOCS_STAGE TO ROLE IDENTIFIER($my_role);
GRANT USAGE ON WAREHOUSE DOCUMENT_AI_WH TO ROLE IDENTIFIER($my_role);

-- Step 7: Insert Sample Document Class (Optional)
-- ============================================================================
-- This creates a sample invoice class with common extraction fields

INSERT INTO CLASS_PROMPTS (class_name, prompts)
SELECT 'invoice', PARSE_JSON('{
  "invoice_number": "What is the invoice number?",
  "invoice_date": "What is the invoice date?",
  "due_date": "What is the due date or payment due date?",
  "vendor_name": "Who is the vendor or supplier?",
  "vendor_address": "What is the vendor address?",
  "customer_name": "Who is the customer or bill to?",
  "total_amount": "What is the total amount or grand total?",
  "tax_amount": "What is the tax amount?",
  "subtotal": "What is the subtotal before tax?",
  "payment_terms": "What are the payment terms?"
}')
WHERE NOT EXISTS (SELECT 1 FROM CLASS_PROMPTS WHERE class_name = 'invoice');

-- Step 8: Verification Queries
-- ============================================================================
-- Run these to verify your setup

SELECT 'Database and Schema' AS object_type, 
       CURRENT_DATABASE() AS database_name,
       CURRENT_SCHEMA() AS schema_name;

SELECT 'Tables' AS object_type, COUNT(*) AS count 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'DOCS';

SELECT 'Stages' AS object_type, COUNT(*) AS count 
FROM INFORMATION_SCHEMA.STAGES 
WHERE STAGE_SCHEMA = 'DOCS';

SELECT 'Document Classes' AS object_type, COUNT(*) AS count 
FROM CLASS_PROMPTS;

-- ============================================================================
-- Setup Complete!
-- ============================================================================
-- You can now deploy the Streamlit application using:
--   snow streamlit deploy --connection keypair-auth
-- ============================================================================

