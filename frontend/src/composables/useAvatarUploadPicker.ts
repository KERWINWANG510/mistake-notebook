import { ref } from "vue";
import { useMessage, type UploadFileInfo } from "naive-ui";
import { isAnimatedAvatarFile, isAvatarCropSupported } from "../utils/avatarImage";

type AvatarUploadPickerOptions = {
  /** 为 true 时仅回调本地文件，由页面在「保存资料」时一并提交 */
  deferSave?: boolean;
};

/** 选择头像文件：静态图进入裁切弹窗，GIF 原图直传。 */
export function useAvatarUploadPicker(
  onUpload: (file: File) => void | Promise<void>,
  options?: AvatarUploadPickerOptions,
) {
  const message = useMessage();
  const cropOpen = ref(false);
  const cropFile = ref<File | null>(null);

  function onUploadChange(payload: { file: UploadFileInfo }) {
    const raw = payload.file.file;
    if (!raw) return;
    if (isAnimatedAvatarFile(raw)) {
      message.info(
        options?.deferSave ? "动图不支持裁切，将在保存资料后上传" : "动图不支持裁切，将按原图上传",
      );
      void onUpload(raw);
      return;
    }
    if (!isAvatarCropSupported(raw)) {
      message.warning("仅支持 JPG、PNG、WebP 格式的裁切上传");
      return;
    }
    cropFile.value = raw;
    cropOpen.value = true;
  }

  async function onCropConfirm(file: File) {
    cropFile.value = null;
    await Promise.resolve(onUpload(file));
  }

  function onCropOpenChange(open: boolean) {
    cropOpen.value = open;
    if (!open) cropFile.value = null;
  }

  return {
    cropOpen,
    cropFile,
    onUploadChange,
    onCropConfirm,
    onCropOpenChange,
  };
}
