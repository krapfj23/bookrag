import { Routes, Route } from "react-router-dom";
import { LibraryScreen } from "./screens/LibraryScreen";
import { UploadScreen } from "./screens/UploadScreen";
import { ReadingScreen } from "./screens/ReadingScreen";
import { BookReadingRedirect } from "./screens/BookReadingRedirect";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryScreen />} />
      <Route path="/upload" element={<UploadScreen />} />
      <Route path="/books/:bookId/read" element={<BookReadingRedirect />} />
      <Route path="/books/:bookId/read/:chapterNum" element={<ReadingScreen />} />
    </Routes>
  );
}
