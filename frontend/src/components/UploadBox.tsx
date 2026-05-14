import type { ChangeEvent } from 'react';

type UploadBoxProps = {
  handleFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  handleUpload: () => Promise<void>;
  uploadLabel: string;
};

export default function UploadBox({ handleFileChange, handleUpload, uploadLabel }: UploadBoxProps) {
  return (
    <section className="upload-box">
      <label htmlFor="document-upload">Choose PDF or TXT</label>
      <input id="document-upload" type="file" accept=".pdf,.txt" onChange={handleFileChange} />
      <button onClick={() => void handleUpload()}>{uploadLabel}</button>
    </section>
  );
}
