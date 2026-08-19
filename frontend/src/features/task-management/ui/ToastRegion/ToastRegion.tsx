import { CheckCircle2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { TASK_TOAST_EVENT } from "../../model/toast";
import styles from "../task-management.module.css";

export const ToastRegion = () => {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    const listener = (event: Event) => {
      setMessage((event as CustomEvent<{ message?: string }>).detail?.message ?? null);
    };
    window.addEventListener(TASK_TOAST_EVENT, listener);
    return () => window.removeEventListener(TASK_TOAST_EVENT, listener);
  }, []);
  useEffect(() => {
    if (!message) return;
    const id = window.setTimeout(() => setMessage(null), 4_000);
    return () => window.clearTimeout(id);
  }, [message]);
  return <div className={styles.toastRegion} role="status" aria-live="polite" aria-atomic="true">{message && <div><CheckCircle2 size={16} /><span>{message}</span><button type="button" aria-label="Dismiss notification" onClick={() => setMessage(null)}><X size={14} /></button></div>}</div>;
};
