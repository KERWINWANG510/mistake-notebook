import defaultFemaleUrl from "../assets/avatars/default_female.svg";
import defaultMaleUrl from "../assets/avatars/default_male.svg";

/** 未上传自定义头像时使用的内置静态图（与后端默认逻辑一致：未设性别为男）。 */
export function defaultAvatarPublicUrl(gender: string | null | undefined): string {
  return gender === "female" ? defaultFemaleUrl : defaultMaleUrl;
}
