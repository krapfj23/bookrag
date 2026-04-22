import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Dropzone } from "./Dropzone";

function makeFile(name = "a.epub"): File {
  return new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], name, {
    type: "application/epub+zip",
  });
}

describe("Dropzone", () => {
  it("renders idle copy by default", () => {
    render(<Dropzone state="idle" onFile={() => {}} />);
    expect(screen.getByText(/drop your epub/i)).toBeInTheDocument();
    expect(screen.getByText(/browse files/i)).toBeInTheDocument();
    expect(screen.getByText(/epub up to 500/i)).toBeInTheDocument();
  });

  it("renders hover copy when state='hover'", () => {
    render(<Dropzone state="hover" onFile={() => {}} />);
    expect(screen.getByText(/drop it here/i)).toBeInTheDocument();
  });

  it("renders the filename when state='uploading'", () => {
    render(
      <Dropzone
        state="uploading"
        filename="a-christmas-carol.epub"
        onFile={() => {}}
      />,
    );
    expect(screen.getByText("a-christmas-carol.epub")).toBeInTheDocument();
    expect(screen.getByText(/uploading/i)).toBeInTheDocument();
  });

  it("renders the filename and a done marker when state='done'", () => {
    render(
      <Dropzone state="done" filename="a-christmas-carol.epub" onFile={() => {}} />,
    );
    expect(screen.getByText("a-christmas-carol.epub")).toBeInTheDocument();
    expect(screen.getByText(/uploaded/i)).toBeInTheDocument();
  });

  it("renders errorMessage when state='error'", () => {
    render(
      <Dropzone
        state="error"
        errorMessage="Only .epub files are accepted"
        onFile={() => {}}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      /only \.epub files are accepted/i,
    );
  });

  it("calls onFile when a file is dropped", () => {
    const onFile = vi.fn();
    render(<Dropzone state="idle" onFile={onFile} />);
    const zone = screen.getByTestId("dropzone");
    fireEvent.drop(zone, {
      dataTransfer: { files: [makeFile("x.epub")] },
    });
    expect(onFile).toHaveBeenCalledTimes(1);
    expect(onFile.mock.calls[0][0].name).toBe("x.epub");
  });

  it("calls onFile when a file is selected via the hidden input", () => {
    const onFile = vi.fn();
    render(<Dropzone state="idle" onFile={onFile} />);
    const input = screen.getByTestId("dropzone-input") as HTMLInputElement;
    const file = makeFile("b.epub");
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("does not call onFile on drop when state is 'uploading'", () => {
    const onFile = vi.fn();
    render(<Dropzone state="uploading" filename="x.epub" onFile={onFile} />);
    const zone = screen.getByTestId("dropzone");
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile("y.epub")] } });
    expect(onFile).not.toHaveBeenCalled();
  });
});
