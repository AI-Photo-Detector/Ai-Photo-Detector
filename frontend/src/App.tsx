import { useEffect, useState } from "react";
import { Upload, FileText, Download, Info, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Progress } from "./components/ui/progress";
import { Badge } from "./components/ui/badge";
import { UploadZone } from "./components/UploadZone";
import { ResultsDashboard } from "./components/ResultsDashboard";
import { HowToGuide } from "./components/HowToGuide";
import { exportToPDF } from "./utils/pdfExport";
import { detectImage } from "./api/detector";

export interface AnalysisResult {
  id: string;
  fileName: string;
  fileSize: number;
  uploadDate: Date;
  isAIGenerated: boolean;
  confidence: number;
  indicators: {
    label: string;
    value: number;
    status: "pass" | "warning" | "fail";
  }[];
  imageUrl: string;
}

export default function App() {
  const [currentTab, setCurrentTab] = useState<"upload" | "results" | "guide">("upload");
  const [currentResult, setCurrentResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastUploadedFile, setLastUploadedFile] = useState<File | null>(null);

  useEffect(() => {
    return () => {
      if (currentResult?.imageUrl) {
        URL.revokeObjectURL(currentResult.imageUrl);
      }
    };
  }, [currentResult]);

  const handleFileUpload = async (files: File[]) => {
    // Prevent spamming uploads while a request is already running
    if (!files.length || isAnalyzing) {
      return;
    }

    const file = files[0];
    setLastUploadedFile(file);
    setIsAnalyzing(true);
    setUploadError(null);

    try {
      const response = await detectImage(file);
      const previewUrl = URL.createObjectURL(file);

      setCurrentResult((previous) => {
        if (previous?.imageUrl) {
          URL.revokeObjectURL(previous.imageUrl);
        }

        return {
          id: response.metadata?.requestId ?? Date.now().toString(),
          fileName: file.name,
          fileSize: file.size,
          uploadDate: new Date(),
          isAIGenerated: response.isAIGenerated,
          confidence: response.confidence,
          indicators: response.indicators,
          imageUrl: previewUrl,
        };
      });

      setCurrentTab("results");
    } catch (error: any) {
      let message = "Analysis failed. Please try again.";

      // Many API clients attach status here (axios-style), but this is safe even if undefined
      const status = error?.response?.status ?? error?.status;

      if (status === 422) {
        message = "Invalid file. Please upload a JPG, PNG, or WEBP image under 10MB.";
      } else if (status === 415) {
        message = "Unsupported file type. Please upload a JPG, PNG, or WEBP image.";
      } else if (
        typeof error?.message === "string" &&
        (error.message.includes("Failed to fetch") ||
          error.message.includes("NetworkError") ||
          error.message.includes("ECONNREFUSED"))
      ) {
        message = "Cannot connect to backend. Make sure the server is running.";
      } else if (error instanceof Error && error.message) {
        message = error.message;
      }

      setUploadError(message);
      setCurrentTab("upload");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRetry = () => {
    if (lastUploadedFile) {
      void handleFileUpload([lastUploadedFile]);
    }
  };

  const handleExportPDF = () => {
    if (currentResult) {
      exportToPDF(currentResult);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#b690e6] via-[#a280cc] to-[#8d70b3]">
      <header className="bg-white/80 backdrop-blur-md border-b border-[#8d70b3]/30 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-[#8d70b3] to-[#655080] rounded-lg flex items-center justify-center shadow-md">
                <FileText className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-gray-900">AI Photo Detector</h1>
                <p className="text-sm text-[#655080]">Detect AI-generated images with confidence</p>
              </div>
            </div>
            <div className="flex items-center gap-2">{currentResult && <Badge variant="secondary">1 Analysis</Badge>}</div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Tabs value={currentTab} onValueChange={(v) => setCurrentTab(v as "upload" | "results" | "guide")} className="space-y-6">
          <TabsList className="grid w-full max-w-md mx-auto grid-cols-3 bg-white/70 backdrop-blur-sm shadow-sm">
            <TabsTrigger value="upload" className="flex items-center gap-2">
              <Upload className="w-4 h-4" />
              Upload
            </TabsTrigger>
            <TabsTrigger value="results" className="flex items-center gap-2" disabled={!currentResult}>
              <FileText className="w-4 h-4" />
              Results
            </TabsTrigger>
            <TabsTrigger value="guide" className="flex items-center gap-2">
              <Info className="w-4 h-4" />
              How to Use
            </TabsTrigger>
          </TabsList>

          <TabsContent value="upload" className="space-y-6">
            <Card className="p-8 shadow-lg border-[#8d70b3]/30 bg-white/70 backdrop-blur-sm">
              <div className="text-center mb-6">
                <h2 className="text-gray-900 mb-2">Upload Photos for Analysis</h2>
                <p className="text-gray-600">Upload one or more images to detect if they were generated by AI</p>
              </div>

              <UploadZone onUpload={handleFileUpload} isAnalyzing={isAnalyzing} />

              {isAnalyzing && (
                <div className="mt-6 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Analyzing images...</span>
                    <span className="text-gray-900">Processing</span>
                  </div>
                  <Progress value={66} className="h-2" />
                </div>
              )}

              {uploadError && (
                <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-4 text-left">
                  <p className="text-sm text-rose-700">{uploadError}</p>
                  <div className="mt-3">
                    <Button type="button" variant="outline" onClick={handleRetry} disabled={isAnalyzing || !lastUploadedFile}>
                      Retry last upload
                    </Button>
                  </div>
                </div>
              )}
            </Card>

            {currentResult && (
              <Card className="p-6 bg-gradient-to-br from-[#b690e6]/50 to-[#a280cc]/50 border-[#8d70b3] shadow-md">
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-[#655080] mt-0.5" />
                  <div>
                    <p className="text-gray-900">Analysis complete</p>
                    <Button variant="link" className="p-0 h-auto text-[#655080]" onClick={() => setCurrentTab("results")}>
                      View results -&gt;
                    </Button>
                  </div>
                </div>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="results">
            {currentResult ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-gray-900">Analysis Results</h2>
                    <p className="text-gray-600">Detailed detection report for your uploaded image</p>
                  </div>
                  <Button onClick={handleExportPDF} className="gap-2 bg-gradient-to-r from-[#8d70b3] to-[#655080] hover:from-[#796099] hover:to-[#514066] shadow-md">
                    <Download className="w-4 h-4" />
                    Export PDF Report
                  </Button>
                </div>

                <ResultsDashboard results={[currentResult]} selectedResult={currentResult} onSelectResult={() => {}} />
              </div>
            ) : (
              <Card className="p-12 text-center shadow-lg bg-white/70 backdrop-blur-sm">
                <AlertCircle className="w-12 h-12 text-[#8d70b3] mx-auto mb-4" />
                <h3 className="text-gray-900 mb-2">No Results Yet</h3>
                <p className="text-gray-600 mb-4">Upload images to see detection results</p>
                <Button onClick={() => setCurrentTab("upload")}>Go to Upload</Button>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="guide">
            <HowToGuide />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}