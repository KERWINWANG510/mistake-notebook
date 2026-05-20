/** 头像裁切导出尺寸（正方形） */
export const AVATAR_CROP_OUTPUT_SIZE = 512;

const CROPPABLE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export function isAvatarCropSupported(file: File): boolean {
  return CROPPABLE_TYPES.has(file.type);
}

export function isAnimatedAvatarFile(file: File): boolean {
  return file.type === "image/gif";
}

export function readFileAsObjectUrl(file: File): string {
  return URL.createObjectURL(file);
}

export function canvasToAvatarFile(
  canvas: HTMLCanvasElement,
  sourceName: string,
  mime: "image/jpeg" | "image/png" | "image/webp" = "image/jpeg",
): Promise<File> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("头像导出失败"));
          return;
        }
        const ext = mime === "image/png" ? "png" : mime === "image/webp" ? "webp" : "jpg";
        const base = sourceName.replace(/\.[^.]+$/, "") || "avatar";
        resolve(new File([blob], `${base}-cropped.${ext}`, { type: mime }));
      },
      mime,
      0.92,
    );
  });
}
