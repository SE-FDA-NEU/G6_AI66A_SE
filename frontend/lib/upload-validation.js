// BR01 uses binary megabytes consistently for both file and batch limits.
export const MB = 1024 * 1024;
export const MAX_FILES = 5;
export const MAX_FILE_BYTES = 5 * MB;
export const MAX_BATCH_BYTES = 50 * MB;
export const ACCEPTED_EXTENSIONS = ['pdf', 'docx', 'pptx'];

export function batchErrors(files) {
  const errors = [];
  if (files.length > MAX_FILES) errors.push('Tối đa 5 tệp mỗi lần.');
  if (files.reduce((total, file) => total + file.size, 0) > MAX_BATCH_BYTES) {
    errors.push('Tổng dung lượng vượt quá 50 MB.');
  }
  return errors;
}

// Existing valid selections take priority; rejected files never consume capacity.
export function validateFile(file, accepted) {
  const extension = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
  const errors = [];
  if (!ACCEPTED_EXTENSIONS.includes(extension)) errors.push('Chỉ chấp nhận PDF, DOCX hoặc PPTX.');
  if (file.size === 0) errors.push('Tệp không được rỗng.');
  if (file.size > MAX_FILE_BYTES) errors.push('Tệp vượt quá 5 MB.');
  return [...errors, ...batchErrors([...accepted, file])];
}

export function validateSelection(entries) {
  const accepted = [];
  return entries.map(entry => {
    const errors = validateFile(entry.file, accepted);
    if (errors.length === 0) accepted.push(entry.file);
    return { ...entry, errors };
  });
}
