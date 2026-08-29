import React, { useRef, useState, useEffect, useCallback } from "react";
import { Video, Square, RotateCcw, Upload, Check, Loader2, AlertCircle, CircleDot } from "lucide-react";
import { Button } from "@/components/ui/button";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";

export default function VideoRecorder({ onUploaded, accent = "#ff5722", maxDurationSec = 120, minDurationSec = 10, maxSizeMb = 200 }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const fileInputRef = useRef(null);

  const [state, setState] = useState("idle"); // idle|live|recording|recorded|uploading|done
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [blob, setBlob] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [progress, setProgress] = useState(0);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  useEffect(() => () => { stopStream(); if (timerRef.current) clearInterval(timerRef.current); }, [stopStream]);

  const startCamera = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 720 } }, audio: true,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.muted = true;
        await videoRef.current.play().catch(() => {});
      }
      setState("live");
    } catch (e) {
      if (e.name === "NotAllowedError") setError("Camera & microphone permission denied. Please allow access and try again.");
      else if (e.name === "NotFoundError") setError("No camera found. Try uploading a video file instead.");
      else setError("Could not access camera. Try uploading a video file instead.");
    }
  };

  const startRecording = () => {
    chunksRef.current = [];
    let mimeType = "video/webm;codecs=vp9,opus";
    if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = "video/webm";
    if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = "";
    const recorder = new MediaRecorder(streamRef.current, mimeType ? { mimeType } : undefined);
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    recorder.onstop = () => {
      const b = new Blob(chunksRef.current, { type: "video/webm" });
      setBlob(b);
      setPreviewUrl(URL.createObjectURL(b));
      setState("recorded");
    };
    recorder.start();
    recorderRef.current = recorder;
    setSeconds(0);
    setState("recording");
    timerRef.current = setInterval(() => setSeconds((s) => {
      if (s >= maxDurationSec) { stopRecording(); return s; }
      return s + 1;
    }), 1000);
  };

  const stopRecording = () => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
    if (timerRef.current) clearInterval(timerRef.current);
    stopStream();
    // Enforce min duration on manual stop
    if (seconds < minDurationSec) {
      setError(`Please record at least ${minDurationSec} seconds. Try again.`);
    }
  };

  const retake = () => {
    setBlob(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setSeconds(0);
    startCamera();
  };

  const uploadBlob = async (fileBlob, filename) => {
    setState("uploading");
    setProgress(0);
    const form = new FormData();
    form.append("file", fileBlob, filename);
    try {
      const { data } = await api.post("/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => setProgress(Math.round((e.loaded / (e.total || 1)) * 100)),
      });
      setState("done");
      onUploaded(data.url);
      toast.success("Video uploaded!");
    } catch (e) {
      setError(formatApiError(e));
      setState("recorded");
    }
  };

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("video/")) { setError("Please select a video file."); return; }
    if (file.size > maxSizeMb * 1024 * 1024) { setError(`Video is too large. Max ${maxSizeMb} MB.`); return; }
    if (file.size > 80 * 1024 * 1024) { setError("Video too large (max 80MB)."); return; }
    setError("");
    uploadBlob(file, file.name);
  };

  const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="w-full" data-testid="video-recorder">
      <div className="relative w-full rounded-2xl overflow-hidden bg-black" style={{ aspectRatio: "3/4", maxHeight: 420 }}>
        {(state === "live" || state === "recording") && (
          <video ref={videoRef} playsInline muted className="w-full h-full object-cover" />
        )}
        {(state === "recorded" || state === "uploading" || state === "done") && previewUrl && (
          <video src={previewUrl} controls playsInline className="w-full h-full object-cover" />
        )}
        {state === "idle" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 p-6 text-center">
            <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: accent }}>
              <Video size={28} className="text-white" />
            </div>
            <p className="text-white/70 text-sm">Record a short video testimonial<br />(up to 2 minutes)</p>
          </div>
        )}
        {state === "recording" && (
          <>
            <div className="absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/60 backdrop-blur">
              <CircleDot size={14} className="text-red-500 animate-pulse" />
              <span className="text-white text-sm font-mono" data-testid="record-timer">
                {fmt(seconds)} / {fmt(maxDurationSec)}
              </span>
            </div>
            {maxDurationSec - seconds <= 10 && maxDurationSec - seconds > 0 && (
              <div className="absolute top-3 right-3 px-3 py-1.5 rounded-full bg-yellow-500/90 text-black text-xs font-semibold animate-pulse" data-testid="record-warning">
                Auto-stopping in {maxDurationSec - seconds}s
              </div>
            )}
          </>
        )}
        {state === "uploading" && (
          <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center gap-3">
            <Loader2 className="animate-spin text-white" size={28} />
            <div className="w-40 h-1.5 rounded-full bg-white/20 overflow-hidden">
              <div className="h-full" style={{ width: `${progress}%`, background: accent }} />
            </div>
            <span className="text-white/80 text-sm">Uploading… {progress}%</span>
          </div>
        )}
        {state === "done" && (
          <div className="absolute top-3 right-3 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-green-500 text-white text-xs font-semibold">
            <Check size={14} /> Uploaded
          </div>
        )}
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 text-sm text-destructive" data-testid="recorder-error">
          <AlertCircle size={16} className="mt-0.5 flex-shrink-0" /> {error}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {state === "idle" && (
          <>
            <Button type="button" onClick={startCamera} data-testid="start-camera-btn" className="gap-2" style={{ background: accent }}>
              <Video size={16} /> Open camera
            </Button>
            <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()} data-testid="upload-video-btn" className="gap-2">
              <Upload size={16} /> Upload a video
            </Button>
          </>
        )}
        {state === "live" && (
          <Button type="button" onClick={startRecording} data-testid="record-btn" className="gap-2" style={{ background: accent }}>
            <CircleDot size={16} /> Start recording
          </Button>
        )}
        {state === "recording" && (
          <Button type="button" onClick={stopRecording} data-testid="stop-btn" variant="destructive" className="gap-2">
            <Square size={16} /> Stop recording
          </Button>
        )}
        {state === "recorded" && (
          <>
            <Button type="button" onClick={() => uploadBlob(blob, "testimonial.webm")} data-testid="submit-video-btn" className="gap-2" style={{ background: accent }}>
              <Check size={16} /> Use this video
            </Button>
            <Button type="button" variant="outline" onClick={retake} data-testid="retake-btn" className="gap-2">
              <RotateCcw size={16} /> Retake
            </Button>
          </>
        )}
        {state === "done" && (
          <Button type="button" variant="outline" onClick={() => { onUploaded(null); setState("idle"); setBlob(null); setPreviewUrl(null); }} className="gap-2">
            <RotateCcw size={16} /> Record again
          </Button>
        )}
      </div>
      <input ref={fileInputRef} type="file" accept="video/*" className="hidden" onChange={handleFile} data-testid="video-file-input" />
    </div>
  );
}
