import { useCallback, useState } from "react";
import { Upload, Image as ImageIcon, X } from "lucide-react";
import { Button } from "./ui/button";

interface UploadZoneProps {
  onUpload: (files: File[]) => void;
  isAnalyzing: boolean;
}

export function UploadZone({ onUpload, isAnalyzing }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files).filter(file =>
      file.type.startsWith("image/")
    );
    
    if (files.length > 0) {
      setSelectedFiles(files);
    }
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setSelectedFiles(files);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(files => files.filter((_, i) => i !== index));
  };

  const handleAnalyze = () => {
    if (selectedFiles.length > 0) {
      onUpload(selectedFiles);
      setSelectedFiles([]);
    }
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-all duration-200 ${
          isDragging
            ? "border-[#8d70b3] bg-[#b690e6]/50 scale-[1.02]"
            : "border-[#8d70b3]/50 bg-gradient-to-br from-[#f5f0ff]/50 to-[#b690e6]/50 hover:border-[#8d70b3] hover:shadow-md"
        }`}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          accept="image/*"
          multiple
          onChange={handleFileInput}
          disabled={isAnalyzing}
        />
        
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 bg-gradient-to-br from-[#8d70b3] to-[#655080] rounded-full flex items-center justify-center shadow-md">
            <Upload className="w-8 h-8 text-white" />
          </div>
          
          <div>
            <p className="text-gray-900 mb-1">
              Drag and drop images here
            </p>
            <p className="text-sm text-[#655080]">
              or click to browse your files
            </p>
          </div>
          
          <label htmlFor="file-upload">
            <Button type="button" variant="outline" disabled={isAnalyzing} asChild>
              <span>Browse Files</span>
            </Button>
          </label>
          
          <p className="text-xs text-gray-500">
            Supports: JPG, PNG, WEBP, GIF (Max 10MB per file)
          </p>
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-700">
              {selectedFiles.length} {selectedFiles.length === 1 ? "file" : "files"} selected
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedFiles([])}
              className="text-[#655080] hover:text-[#514066] hover:bg-[#b690e6]/30"
            >
              Clear all
            </Button>
          </div>

          <div className="space-y-2 max-h-48 overflow-y-auto">
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 bg-white border border-[#8d70b3]/30 rounded-lg shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="w-10 h-10 bg-gradient-to-br from-[#b690e6] to-[#8d70b3] rounded flex items-center justify-center flex-shrink-0">
                  <ImageIcon className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-900 truncate">{file.name}</p>
                  <p className="text-xs text-[#655080]">
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
            {isAnalyzing ? "Analyzing..." : "Analyze Images"}
          </Button>
        </div>
      )}
    </div>
  );
}