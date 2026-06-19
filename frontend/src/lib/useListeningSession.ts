import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listeningApi } from "./api";
import type { ListeningSessionStatus, ListeningStep } from "../types";

export function useListeningSession(sessionId: number) {
  const queryClient = useQueryClient();

  const sessionQuery = useQuery({
    queryKey: ["listening-session", sessionId],
    queryFn: () => listeningApi.getSession(sessionId),
    enabled: Number.isFinite(sessionId) && sessionId > 0,
  });

  const scriptId = sessionQuery.data?.script_id;
  const scriptQuery = useQuery({
    queryKey: ["listening-script", scriptId],
    queryFn: () => listeningApi.getScript(scriptId!),
    enabled: !!scriptId,
  });

  const updateMutation = useMutation({
    mutationFn: (
      payload: Partial<{
        current_step: ListeningStep;
        playback_speed: number;
        dictation_level: number;
        status: ListeningSessionStatus;
      }>,
    ) => listeningApi.updateSession(sessionId, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["listening-session", sessionId], updated);
    },
  });

  const attemptMutation = useMutation({
    mutationFn: (payload: { line_id: number; dictation_level: number; user_text: string }) =>
      listeningApi.recordAttempt(sessionId, payload),
  });

  return {
    session: sessionQuery.data,
    sessionLoading: sessionQuery.isLoading,
    script: scriptQuery.data,
    scriptLoading: scriptQuery.isLoading,
    setStep: (step: ListeningStep) => updateMutation.mutate({ current_step: step }),
    setPlaybackSpeed: (speed: number) => updateMutation.mutate({ playback_speed: speed }),
    setDictationLevel: (level: number) => updateMutation.mutate({ dictation_level: level }),
    complete: () => updateMutation.mutate({ status: "completed" }),
    recordAttempt: (payload: { line_id: number; dictation_level: number; user_text: string }) =>
      attemptMutation.mutateAsync(payload),
    attemptPending: attemptMutation.isPending,
    refetchScript: () => queryClient.invalidateQueries({ queryKey: ["listening-script", scriptId] }),
  };
}
