-- database/migration_add_verified_to_document_chunks.sql
-- Thêm cột verified cho document_chunks, mặc định 1 (True) để chunk cũ không bị ảnh hưởng

IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'document_chunks' AND COLUMN_NAME = 'verified'
)
BEGIN
    ALTER TABLE document_chunks 
    ADD verified BIT NOT NULL CONSTRAINT DF_document_chunks_verified DEFAULT 1;
END
GO

