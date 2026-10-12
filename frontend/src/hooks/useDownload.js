import { useEffect, useRef, useState } from "react";
import { startDownload, watchProgress, fetchJobFile, saveBlobAsFile } from "../api/client";


export function useDownload() {
  const [state, setState] = useState({ status: "idle" });
  const stopWatchingRef = useRef(null);

  function start(url) {
    setState({ status: "starting" });

    startDownload(url)
      .then((jobId) => {
        setState({ status: "fetching_info" });

        stopWatchingRef.current = watchProgress(jobId, async (data) => {
          setState(data);

          if (data.status === "done") {
            stopWatchingRef.current?.();
            try {
              const { blob, filename } = await fetchJobFile(jobId);
              saveBlobAsFile(blob, filename);
              setState({ status: "idle" });
            } catch (err) {
              setState({ status: "error", error: err.message });
            }
          } else if (data.status === "error") {
            stopWatchingRef.current?.();
          }
        });
      })
      .catch((err) => {
        setState({ status: "error", error: err.message });
      });
  }

  // Closes the WebSocket if the component unmounts mid-download.
  useEffect(() => {
    return () => stopWatchingRef.current?.();
  }, []);

  return { state, start };
}