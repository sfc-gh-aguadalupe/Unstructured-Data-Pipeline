-- ============================================================================
-- Snowflake Document AI - Cleanup Script
-- ============================================================================
-- WARNING: This script will DELETE all data and objects created by the app
-- Use this to completely remove the Document AI application from Snowflake
-- ============================================================================

-- Confirm you want to proceed
-- Uncomment the following line to enable cleanup
-- SET confirm_cleanup = TRUE;

-- Step 1: Drop Streamlit Application
-- ============================================================================
DROP STREAMLIT IF EXISTS DOCUMENT_AI_DB.DOCS.DOCUMENT_AI_APP;

-- Step 2: Drop Tables (Data will be lost!)
-- ============================================================================
USE SCHEMA DOCUMENT_AI_DB.DOCS;

DROP TABLE IF EXISTS DOCUMENT_OCR;
DROP TABLE IF EXISTS DOCUMENTS_EXTRACTED_FIELDS;
DROP TABLE IF EXISTS DOCUMENTS_PROCESSED;
DROP TABLE IF EXISTS NEW_UPLOADS;
DROP TABLE IF EXISTS CLASS_PROMPTS;

-- Step 3: Drop Stage (Uploaded files will be lost!)
-- ============================================================================
DROP STAGE IF EXISTS MY_DOCS_STAGE;

-- Step 4: Drop Warehouse (Optional - may be shared)
-- ============================================================================
-- Uncomment if you want to remove the warehouse
-- DROP WAREHOUSE IF EXISTS DOCUMENT_AI_WH;

-- Step 5: Drop Schema and Database (Optional - complete removal)
-- ============================================================================
-- Uncomment to completely remove the database
-- DROP SCHEMA IF EXISTS DOCUMENT_AI_DB.DOCS;
-- DROP DATABASE IF EXISTS DOCUMENT_AI_DB;

-- Verification
-- ============================================================================
SHOW STREAMLIT APPS LIKE 'DOCUMENT_AI_APP';
SHOW TABLES IN SCHEMA DOCUMENT_AI_DB.DOCS;
SHOW STAGES IN SCHEMA DOCUMENT_AI_DB.DOCS;

-- ============================================================================
-- Cleanup Complete!
-- ============================================================================
-- To redeploy, run setup_database.sql and redeploy the Streamlit app
-- ============================================================================

