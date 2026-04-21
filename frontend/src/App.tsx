import { Routes, Route } from "react-router-dom";
import { LibraryScreen } from "./screens/LibraryScreen";
import { UploadScreen } from "./screens/UploadScreen";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryScreen />} />
      <Route path="/upload" element={<UploadScreen />} />
    </Routes>
  );
}
