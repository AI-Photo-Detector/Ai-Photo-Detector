import { type CSSProperties, useEffect, useState } from "react";
import {
  AlertTriangle,
  FileSearch,
  Moon,
  RefreshCw,
  Sun,
  UploadCloud,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "./components/ui/tabs";
import { Progress } from "./components/ui/progress";
import { UploadZone } from "./components/UploadZone";
import { ResultsDashboard } from "./components/ResultsDashboard";
import { HowToGuide } from "./components/HowToGuide";
import { exportToPDF } from "./utils/pdfExport";
import {
  DetectImageError,
  detectImage,
  type ELAMetadata,
  type ForensicTest,
  type ModelEvidence,
  type ResultReliability,
  type RobustnessCheck,
  type UserSummary,
} from "./api/detector";

/* =======================
   MAIN RESULT TYPE
======================= */
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
    explanation?: string;
  }[];

  forensic_tests?: ForensicTest[];
  modelEvidence?: ModelEvidence;
  robustness?: RobustnessCheck;
  reliability?: ResultReliability;
  officialReport?: string;
  userSummary?: UserSummary;

  imageUrl: string;
  ela?: ELAMetadata;
}

function getUploadErrorMessage(error: unknown) {
  if (error instanceof DetectImageError) {
    if (error.errorCode === "REQUEST_TIMEOUT") {
      return "The backend took too long to respond. Try again in a moment.";
    }

    if (error.errorCode === "BACKEND_OFFLINE" || error.status === 0) {
      return "Cannot connect to the backend. Make sure the API server is running, then try again.";
    }

    if (error.errorCode === "MODEL_UNAVAILABLE") {
      return "Detection model is not available. Add BITMIND_API_KEY to your backend .env file, or enable fallback for local testing.";
    }

    if (error.errorCode === "FILE_TOO_LARGE" || error.status === 413) {
      return "That image is too large. Please upload a JPG, PNG, or WEBP image under 10MB.";
    }

    if (error.errorCode === "UNSUPPORTED_MEDIA_TYPE" || error.status === 415) {
      return "Unsupported file type. Please upload JPG, PNG, or WEBP.";
    }

    if (error.errorCode === "INVALID_IMAGE_CONTENT" || error.status === 422) {
      return "This image could not be read. Try a different JPG, PNG, or WEBP file under 10MB.";
    }

    if (error.errorCode === "INTERNAL_ERROR") {
      return "The backend hit an unexpected error. Please try again or check the API logs.";
    }

    return error.message;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Analysis failed. Please try again.";
}

/* =======================
   MAIN COMPONENT
======================= */
export default function App() {
  const [currentTab, setCurrentTab] = useState<
    "upload" | "results" | "guide"
  >("upload");

  const [currentResult, setCurrentResult] =
    useState<AnalysisResult | null>(null);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem("ai-photo-detector-theme") === "dark";
  });
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastUploadedFile, setLastUploadedFile] =
    useState<File | null>(null);

  /* =======================
     CLEAN UP IMAGE MEMORY
  ======================= */
  useEffect(() => {
    window.localStorage.setItem(
      "ai-photo-detector-theme",
      isDarkMode ? "dark" : "light"
    );
  }, [isDarkMode]);

  useEffect(() => {
    return () => {
      if (currentResult?.imageUrl) {
        URL.revokeObjectURL(currentResult.imageUrl);
      }
    };
  }, [currentResult]);

  useEffect(() => {
    if (!isAnalyzing) {
      setAnalysisProgress(0);
      return;
    }

    setAnalysisProgress(8);
    const interval = window.setInterval(() => {
      setAnalysisProgress((previous) => {
        if (previous >= 92) {
          return previous;
        }

        const nextStep = previous < 35 ? 9 : previous < 70 ? 5 : 2;
        return Math.min(92, previous + nextStep);
      });
    }, 550);

    return () => {
      window.clearInterval(interval);
    };
  }, [isAnalyzing]);

  /* =======================
     HANDLE FILE UPLOAD
  ======================= */
  const handleFileUpload = async (files: File[]) => {
    if (!files.length || isAnalyzing) return;

    const file = files[0];
    setLastUploadedFile(file);
    setIsAnalyzing(true);
    setUploadError(null);

    try {
      const response = await detectImage(file);
      const previewUrl = URL.createObjectURL(file);
      setAnalysisProgress(100);

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

          forensic_tests: response.forensic_tests,
          modelEvidence: response.metadata?.modelEvidence,
          robustness: response.metadata?.robustness,
          reliability: response.metadata?.reliability,
          officialReport: response.metadata?.officialReport,
          userSummary: response.metadata?.userSummary,

          imageUrl: previewUrl,
          ela: response.metadata?.ela,
        };
      });

      setCurrentTab("results");
    } catch (error) {
      setUploadError(getUploadErrorMessage(error));
      setCurrentTab("upload");
    } finally {
      setIsAnalyzing(false);
    }
  };

  /* =======================
     RETRY UPLOAD
  ======================= */
  const handleRetry = () => {
    if (lastUploadedFile) {
      void handleFileUpload([lastUploadedFile]);
    }
  };

  /* =======================
     EXPORT PDF
  ======================= */
  const handleExportPDF = () => {
    if (currentResult) {
      exportToPDF(currentResult);
    }
  };

  const isResultsView = currentTab === "results";
  const progressLabel =
    analysisProgress < 35
      ? "Preparing image..."
      : analysisProgress < 70
        ? "Running forensic checks..."
        : analysisProgress < 95
          ? "Building report..."
          : "Finishing...";
  const theme = isDarkMode
    ? {
        pageBackground:
          "linear-gradient(180deg, #15111d 0%, #20172e 42%, #2f2143 100%)",
        headerBackground: "#17121f",
        headerBorder: "rgba(226, 214, 244, 0.12)",
        iconBackground: "#241a33",
        iconBorder: "rgba(226, 214, 244, 0.16)",
        iconColor: "#d6c1f3",
        heading: "#faf7ff",
        mutedText: "#c9b9dc",
        tabBackground: "rgba(32, 23, 46, 0.72)",
        tabBorder: "rgba(226, 214, 244, 0.12)",
        tabShadow: "0 12px 30px rgba(0, 0, 0, 0.18)",
        cardBackground: "rgba(27, 20, 38, 0.92)",
        cardBorder: "rgba(226, 214, 244, 0.13)",
        panelBackground: "rgba(30, 23, 43, 0.86)",
        panelBorder: "rgba(226, 214, 244, 0.14)",
        panelShadow: "0 18px 42px rgba(0, 0, 0, 0.24)",
        mutedPanelBackground: "rgba(44, 34, 61, 0.66)",
        mutedPanelBorder: "rgba(226, 214, 244, 0.12)",
      }
    : {
        pageBackground:
          "linear-gradient(180deg, #fbf8ff 0%, #eadcf8 28%, #c9a9e6 100%)",
        headerBackground: "#ffffff",
        headerBorder: "rgba(91, 73, 115, 0.14)",
        iconBackground: "#f4effb",
        iconBorder: "rgba(101, 80, 128, 0.16)",
        iconColor: "#655080",
        heading: "#211a2b",
        mutedText: "#6b5a80",
        tabBackground: "rgba(255, 255, 255, 0.5)",
        tabBorder: "rgba(101, 80, 128, 0.14)",
        tabShadow: "0 10px 26px rgba(61, 48, 77, 0.08)",
        cardBackground: "#ffffff",
        cardBorder: "rgba(141, 112, 179, 0.3)",
        panelBackground: "rgba(255, 255, 255, 0.78)",
        panelBorder: "rgba(141, 112, 179, 0.3)",
        panelShadow: "0 18px 42px rgba(61, 48, 77, 0.14)",
        mutedPanelBackground: "rgba(245, 240, 255, 0.58)",
        mutedPanelBorder: "rgba(141, 112, 179, 0.24)",
      };
  const appStyle = {
    background: theme.pageBackground,
    color: theme.heading,
    "--app-card-bg": theme.cardBackground,
    "--app-card-border": theme.cardBorder,
    "--app-panel-bg": theme.panelBackground,
    "--app-panel-border": theme.panelBorder,
    "--app-panel-shadow": theme.panelShadow,
    "--app-muted-panel-bg": theme.mutedPanelBackground,
    "--app-muted-panel-border": theme.mutedPanelBorder,
  } as CSSProperties;

  /* =======================
     UI
  ======================= */
  return (
    <div
      className={`min-h-screen ${isDarkMode ? "dark" : ""}`}
      style={appStyle}
    >
      <header
        className="border-b sticky top-0 z-10"
        style={{
          background: theme.headerBackground,
          borderColor: theme.headerBorder,
        }}
      >
        <div
          className="mx-auto px-4 flex justify-between items-center"
          style={{
            maxWidth: isResultsView ? "none" : "80rem",
            minHeight: "72px",
          }}
        >
          <div className="flex gap-3 items-center">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{
                background: theme.iconBackground,
                border: `1px solid ${theme.iconBorder}`,
                color: theme.iconColor,
              }}
            >
              <FileSearch className="w-5 h-5" />
            </div>
            <div>
              <h1 style={{ color: theme.heading, fontSize: "1.05rem", fontWeight: 650 }}>
                AI Photo Detector
              </h1>
              <p className="text-sm" style={{ color: theme.mutedText }}>
                Image authenticity analysis
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {currentResult && (
              <span
                className="text-sm"
                style={{ color: theme.mutedText, fontWeight: 500 }}
              >
                Analysis ready
              </span>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-pressed={isDarkMode}
              onClick={() => setIsDarkMode((current) => !current)}
              style={{
                borderColor: theme.headerBorder,
                background: isDarkMode ? "#221831" : "#fbf8ff",
                color: theme.heading,
              }}
            >
              {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              {isDarkMode ? "Light" : "Dark"}
            </Button>
          </div>
        </div>
      </header>

      <main
        className="mx-auto px-4 py-8"
        style={{
          maxWidth: isResultsView ? "none" : "80rem",
          width: "100%",
        }}
      >
        <Tabs
          value={currentTab}
          onValueChange={(v: string) =>
            setCurrentTab(v as "upload" | "results" | "guide")
          }
        >
          <TabsList
            className="grid grid-cols-3 max-w-md mx-auto"
            style={{
              background: theme.tabBackground,
              border: `1px solid ${theme.tabBorder}`,
              boxShadow: theme.tabShadow,
            }}
          >
            <TabsTrigger value="upload">Upload</TabsTrigger>
            <TabsTrigger value="results" disabled={!currentResult}>
              Results
            </TabsTrigger>
            <TabsTrigger value="guide">Guide</TabsTrigger>
          </TabsList>

          {/* =======================
             UPLOAD TAB
          ======================= */}
          <TabsContent value="upload">
            <Card
              className="p-8 text-center"
              style={{
                background: theme.cardBackground,
                borderColor: theme.cardBorder,
                boxShadow: theme.panelShadow,
              }}
            >
              <UploadZone
                onUpload={handleFileUpload}
                isAnalyzing={isAnalyzing}
                isDarkMode={isDarkMode}
                hasResult={currentResult !== null}
              />

              {isAnalyzing && (
                <div className="mt-4" style={{ maxWidth: "28rem", marginInline: "auto" }}>
                  <div className="flex justify-between mb-2 text-sm" style={{ color: theme.mutedText }}>
                    <span>{progressLabel}</span>
                    <span>{Math.round(analysisProgress)}%</span>
                  </div>
                  <Progress value={analysisProgress} />
                  <p className="text-xs mt-2" style={{ color: theme.mutedText }}>
                    Checking the model score and supporting forensic signals.
                  </p>
                </div>
              )}

              {uploadError && (
                <div
                  className="mt-4 rounded-lg border p-4 text-left"
                  style={{
                    maxWidth: "36rem",
                    marginInline: "auto",
                    background: isDarkMode ? "rgba(73, 37, 51, 0.88)" : "#fff7ed",
                    borderColor: isDarkMode ? "rgba(251, 191, 36, 0.28)" : "#fed7aa",
                    color: isDarkMode ? "#ffe8b5" : "#9a3412",
                  }}
                >
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p style={{ fontWeight: 700 }}>Analysis could not finish</p>
                      <p className="text-sm" style={{ marginTop: "0.25rem" }}>
                        {uploadError}
                      </p>
                    </div>
                    {lastUploadedFile && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleRetry}
                        disabled={isAnalyzing}
                        style={{
                          borderColor: isDarkMode ? "rgba(255, 232, 181, 0.38)" : "#fed7aa",
                          color: isDarkMode ? "#fff7df" : "#9a3412",
                        }}
                      >
                        <RefreshCw className="w-4 h-4" />
                        Retry
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </Card>
          </TabsContent>

          {/* =======================
             RESULTS TAB
          ======================= */}
          <TabsContent value="results">
            {currentResult ? (
              <>
                <div
                  className="flex justify-between items-center"
                  style={{
                    margin: "1rem auto",
                    width: "min(100%, 1320px)",
                  }}
                >
                  <h2 style={{ color: isDarkMode ? "#faf7ff" : "#211a2b" }}>
                    Analysis Results
                  </h2>
                  <Button onClick={handleExportPDF}>
                    Export PDF
                  </Button>
                </div>

                <ResultsDashboard
                  results={[currentResult]}
                  selectedResult={currentResult}
                  isDarkMode={isDarkMode}
                />
              </>
            ) : (
              <Card
                className="p-8 text-center"
                style={{
                  ...{
                    background: theme.cardBackground,
                    borderColor: theme.cardBorder,
                    boxShadow: theme.panelShadow,
                  },
                  maxWidth: "36rem",
                  margin: "1.25rem auto 0",
                }}
              >
                <div
                  className="w-12 h-12 rounded-lg flex items-center justify-center mx-auto mb-4"
                  style={{
                    background: theme.iconBackground,
                    color: theme.iconColor,
                    border: `1px solid ${theme.iconBorder}`,
                  }}
                >
                  <UploadCloud className="w-6 h-6" />
                </div>
                <h3 style={{ color: theme.heading, fontSize: "1.05rem", fontWeight: 700 }}>
                  No Results Yet
                </h3>
                <p className="text-sm" style={{ color: theme.mutedText, marginTop: "0.35rem" }}>
                  Upload a JPG, PNG, or WEBP image to generate an analysis report.
                </p>
                <Button
                  type="button"
                  onClick={() => setCurrentTab("upload")}
                  style={{ marginTop: "1rem" }}
                >
                  Go to Upload
                </Button>
              </Card>
            )}
          </TabsContent>

          {/* =======================
             GUIDE TAB
          ======================= */}
          <TabsContent value="guide">
            <HowToGuide />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
