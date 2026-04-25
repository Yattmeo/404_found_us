/**
 * useFileValidation Hook - Consolidate file validation logic
 * Reduces complexity in components that handle file uploads
 */
import { useState } from 'react';
import { parseFileData } from '../utils/fileParser';

export const useFileValidation = (requiredColumns) => {
  const [fileName, setFileName] = useState('');
  const [fileError, setFileError] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);
  const [previewData, setPreviewData] = useState([]);
  const [fullData, setFullData] = useState([]);
  const [showPreview, setShowPreview] = useState(false);

  const handleFile = async (file) => {
    setFileName(file.name);
    setFileError('');
    setValidationErrors([]);
    setIsValidating(true);

    try {
      const validation = await parseFileData(file, requiredColumns);

      if (validation.errors.length === 0) {
        setPreviewData(validation.data.slice(0, 10));
        setFullData(validation.data);
        setShowPreview(true);
        setValidationErrors([]);
      } else {
        setValidationErrors(validation.errors);
        setShowPreview(false);
        setFileError(
          `Validation failed: ${validation.errors.length} issue(s) found. Please review the errors below.`
        );
      }
    } catch (error) {
      setFileError(error.message || 'Error processing file');
      setValidationErrors([]);
    } finally {
      setIsValidating(false);
    }
  };

  const handleReupload = () => {
    setFileName('');
    setFileError('');
    setValidationErrors([]);
    setPreviewData([]);
    setFullData([]);
    setShowPreview(false);
  };

  return {
    fileName,
    fileError,
    isValidating,
    validationErrors,
    previewData,
    fullData,
    showPreview,
    handleFile,
    handleReupload,
    setShowPreview,
  };
};
