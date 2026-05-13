import type { GlobalThemeOverrides } from "naive-ui";

/** 全局主题：现代 Indigo 主色、较大圆角与留白 */
export const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#4f46e5",
    primaryColorHover: "#6366f1",
    primaryColorPressed: "#4338ca",
    primaryColorSuppl: "#818cf8",
    borderRadius: "10px",
    borderRadiusSmall: "8px",
    fontSize: "15px",
    fontSizeMedium: "15px",
    fontSizeLarge: "16px",
    heightMedium: "40px",
    lineHeight: 1.55,
  },
  Card: {
    borderRadius: "16px",
    paddingMedium: "22px 24px",
    titleFontSizeMedium: "17px",
    titleFontWeight: "600",
  },
  Button: {
    borderRadiusMedium: "10px",
    fontWeightMedium: "500",
  },
  Input: {
    borderRadius: "10px",
    heightMedium: "40px",
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: "10px",
        heightMedium: "40px",
      },
    },
  },
  DataTable: {
    borderRadius: "12px",
    thColor: "rgba(79, 70, 229, 0.06)",
    thFontWeight: "600",
  },
  Tag: {
    borderRadius: "8px",
  },
  Menu: {
    borderRadius: "10px",
    itemColorActive: "rgba(79, 70, 229, 0.12)",
    itemTextColorActive: "#4f46e5",
    itemTextColorActiveHorizontal: "#4f46e5",
  },
  Modal: {
    borderRadius: "16px",
  },
};
