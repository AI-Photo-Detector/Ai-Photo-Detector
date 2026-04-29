import { type CSSProperties, useCallback, useRef, useState } from "react";
import { AlertCircle, Loader2, Upload, Image as ImageIcon, X } from "lucide-react";
import { Button } from "./ui/button";

interface UploadZoneProps {
  onUpload: (files: File[]) => void;
  isAnalyzing: boolean;
  isDarkMode?: boolean;
  hasResult?: boolean;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

function isAcceptedImage(file: File) {
  const lowerName = file.name.toLowerCase();
  return (
    ACCEPTED_MIME_TYPES.has(file.type) ||
    ACCEPTED_EXTENSIONS.some((extension) => lowerName.endsWith(extension))
  );
}

function validateFiles(files: File[]) {
  if (files.length === 0) {
    return {
      acceptedFiles: [],
      error: "No photo selected yet. Choose a JPG, PNG, or WEBP image to analyze.",
    };
  }

  const acceptedFiles: File[] = [];
  const rejectedMessages: string[] = [];

  files.forEach((file) => {
    if (!isAcceptedImage(file)) {
      rejectedMessages.push(`${file.name} is not a supported image type.`);
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      rejectedMessages.push(`${file.name} is larger than 10MB.`);
      return;
    }

    acceptedFiles.push(file);
  });

  return {
    acceptedFiles,
    error: rejectedMessages[0] ?? null,
  };
}

export function UploadZone({
  onUpload,
  isAnalyzing,
  isDarkMode = false,
  hasResult = false,
}: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [isChooseHovered, setIsChooseHovered] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selectedFileCount = selectedFiles.length;
  const selectedFileLabel =
    selectedFileCount === 1
      ? selectedFiles[0].name
      : `${selectedFileCount} photos selected`;
  const chooseButtonLabel = isAnalyzing
    ? "Analyzing Photo..."
    : selectedFileCount > 0
      ? selectedFileCount === 1
        ? "Change Selected Photo"
        : "Change Selected Photos"
      : hasResult
        ? "Analyze Another Photo"
        : "Choose Photo";
  const analyzeButtonLabel = isAnalyzing
    ? "Analyzing..."
    : selectedFileCount === 1
      ? "Analyze Photo"
      : `Analyze ${selectedFileCount} Photos`;
  const theme = isDarkMode
    ? {
        dropBackground: isDragging
          ? "rgba(126, 94, 169, 0.34)"
          : "linear-gradient(135deg, rgba(38, 29, 54, 0.9), rgba(64, 47, 88, 0.66))",
        dropBorder: isDragging ? "#c9a9e6" : "rgba(214, 193, 243, 0.42)",
        iconBackground: "linear-gradient(135deg, #9b7bd0, #6f5794)",
        heading: "#faf7ff",
        muted: "#c9b9dc",
        alertBackground: "rgba(73, 37, 51, 0.9)",
        alertBorder: "rgba(251, 191, 36, 0.28)",
        alertText: "#ffe8b5",
        fileBackground: "rgba(30, 23, 43, 0.92)",
        fileBorder: "rgba(226, 214, 244, 0.14)",
      }
    : {
        dropBackground: isDragging
          ? "rgba(182, 144, 230, 0.5)"
          : "linear-gradient(135deg, rgba(245, 240, 255, 0.5), rgba(182, 144, 230, 0.5))",
        dropBorder: isDragging ? "#8d70b3" : "rgba(141, 112, 179, 0.5)",
        iconBackground: "linear-gradient(135deg, #8d70b3, #655080)",
        heading: "#111827",
        muted: "#655080",
        alertBackground: "#fff7ed",
        alertBorder: "#fed7aa",
        alertText: "#9a3412",
        fileBackground: "#ffffff",
        fileBorder: "rgba(141, 112, 179, 0.3)",
      };
  const headlineText = isAnalyzing
    ? "Analyzing your photo"
    : selectedFileCount > 0
      ? "Photo ready to analyze"
      : hasResult
        ? "Analyze another photo"
        : "Drop a photo here";
  const helperText = selectedFileCount > 0
    ? selectedFileLabel
    : isAnalyzing
      ? "Please wait while the detector runs."
      : "or choose one from your files";
  const chooseButtonStyle: CSSProperties = {
    borderColor: isChooseHovered
      ? isDarkMode
        ? "#f7f0ff"
        : "#655080"
      : isDarkMode
        ? "rgba(201, 169, 230, 0.72)"
        : "#8d70b3",
    backgroundColor: isChooseHovered
      ? isDarkMode
        ? "#c9a9e6"
        : "#8d70b3"
      : isDarkMode
        ? "#211832"
        : "rgba(255, 255, 255, 0.92)",
    color: isChooseHovered
      ? isDarkMode
        ? "#211832"
        : "#ffffff"
      : isDarkMode
        ? "#f7f0ff"
        : "#655080",
    boxShadow: isChooseHovered
      ? "0 12px 22px rgba(101, 80, 128, 0.26)"
      : "0 4px 10px rgba(101, 80, 128, 0.12)",
    transform: isChooseHovered ? "translateY(-2px)" : "translateY(0)",
    transition:
      "background-color 160ms ease, color 160ms ease, border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease",
  };

  const selectFiles = useCallback((files: File[]) => {
    const { acceptedFiles, error } = validateFiles(files);
    setSelectionError(error);
    setSelectedFiles(acceptedFiles);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (isAnalyzing) return;
    setIsDragging(true);
  }, [isAnalyzing]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (isAnalyzing) return;
    selectFiles(Array.from(e.dataTransfer.files));
  }, [isAnalyzing, selectFiles]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      selectFiles(Array.from(e.target.files));
      e.target.value = "";
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(files => files.filter((_, i) => i !== index));
    setSelectionError(null);
  };

  const handleAnalyze = () => {
    if (selectedFiles.length > 0) {
      onUpload(selectedFiles);
      setSelectedFiles([]);
      setSelectionError(null);
    }
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-all duration-200 ${
          isDragging ? "scale-[1.02]" : "hover:shadow-md"
        }`}
        style={{
          background: theme.dropBackground,
          borderColor: theme.dropBorder,
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          id="file-upload"
          className="hidden"
          accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
          multiple
          onChange={handleFileInput}
          disabled={isAnalyzing}
        />
        
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center shadow-md"
            style={{ background: theme.iconBackground }}
          >
            <Upload className="w-8 h-8 text-white" />
          </div>
          
          <div>
            <p className="mb-1" style={{ color: theme.heading }}>
              {headlineText}
            </p>
            <p
              className="text-sm"
              style={{
                color: theme.muted,
                maxWidth: "22rem",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={selectedFileCount === 1 ? selectedFiles[0].name : undefined}
            >
              {helperText}
            </p>
          </div>
          
          <Button
            type="button"
            variant="outline"
            disabled={isAnalyzing}
            onClick={() => fileInputRef.current?.click()}
            onMouseEnter={() => setIsChooseHovered(true)}
            onMouseLeave={() => setIsChooseHovered(false)}
            onFocus={() => setIsChooseHovered(true)}
            onBlur={() => setIsChooseHovered(false)}
            style={chooseButtonStyle}
          >
            {isAnalyzing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            <span
              style={{
                display: "inline-block",
                maxWidth: "14rem",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {chooseButtonLabel}
            </span>
          </Button>
          
          <p className="text-xs" style={{ color: theme.muted }}>
            Supports: JPG, PNG, WEBP (Max 10MB per file)
          </p>
          {!selectedFiles.length && !selectionError && (
            <p className="text-xs" style={{ color: theme.muted }}>
              {hasResult ? "No new photo selected yet." : "No photo selected yet."}
            </p>
          )}
        </div>
      </div>

      {selectionError && (
        <div
          className="flex items-start gap-2 rounded-lg border p-3 text-left"
          style={{
            background: theme.alertBackground,
            borderColor: theme.alertBorder,
            color: theme.alertText,
          }}
        >
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <p className="text-sm">{selectionError}</p>
        </div>
      )}

      {selectedFiles.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm" style={{ color: theme.heading }}>
              {selectedFiles.length} {selectedFiles.length === 1 ? "file" : "files"} selected
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelectedFiles([]);
                setSelectionError(null);
              }}
              className="text-[#655080] hover:text-[#514066] hover:bg-[#b690e6]/30"
            >
              Clear all
            </Button>
          </div>

          <div className="space-y-2 max-h-48 overflow-y-auto">
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 border rounded-lg shadow-sm hover:shadow-md transition-shadow"
                style={{
                  background: theme.fileBackground,
                  borderColor: theme.fileBorder,
                }}
              >
                <div className="w-10 h-10 bg-gradient-to-br from-[#b690e6] to-[#8d70b3] rounded flex items-center justify-center flex-shrink-0">
                  <ImageIcon className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: theme.heading }}>{file.name}</p>
                  <p className="text-xs" style={{ color: theme.muted }}>
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFile(index)}
                  disabled={isAnalyzing}
                  className="hover:bg-[#b690e6]/30"
                >
                  <X className="w-4 h-4 text-gray-400" />
                </Button>
              </div>
            ))}
          </div>

          <Button
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            className="w-full bg-gradient-to-r from-[#8d70b3] to-[#655080] hover:from-[#796099] hover:to-[#514066] shadow-md"
            size="lg"
          >
            {isAnalyzing && <Loader2 className="w-4 h-4 animate-spin" />}
            {analyzeButtonLabel}
          </Button>
        </div>
      )}
    </div>
  );
}
