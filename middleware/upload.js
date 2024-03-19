import multer from "multer";

// Set up local storage for CSV files
const csvUpload = multer({ dest: "uploads/" });

export { csvUpload };
