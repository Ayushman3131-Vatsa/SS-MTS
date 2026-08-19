import { Outlet } from "react-router-dom";

import { TaskManagementProvider } from "../TaskManagementProvider/TaskManagementProvider";
import { ToastRegion } from "../ToastRegion/ToastRegion";
import styles from "../task-management.module.css";

export const TaskManagementLayout = () => (
  <TaskManagementProvider>
    <div className={styles.workspace}><Outlet /><ToastRegion /></div>
  </TaskManagementProvider>
);
