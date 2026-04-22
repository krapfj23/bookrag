import type { CSSProperties, PropsWithChildren } from "react";

type IconProps = PropsWithChildren<{
  d?: string;
  size?: number;
  stroke?: number;
  fill?: string;
  viewBox?: string;
  style?: CSSProperties;
}>;

export function Icon({
  d,
  size = 16,
  stroke = 1.5,
  fill = "none",
  viewBox = "0 0 16 16",
  style,
  children,
}: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      fill={fill}
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }}
    >
      {d ? <path d={d} /> : children}
    </svg>
  );
}

type Props = Omit<IconProps, "d" | "children" | "viewBox">;

export const IcSearch = (p: Props) => (
  <Icon {...p} d="M7.5 12.5a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm3.5-1.5l2.5 2.5" />
);
export const IcPlus = (p: Props) => <Icon {...p} d="M8 3v10M3 8h10" />;
export const IcSun = (p: Props) => (
  <Icon {...p}>
    <circle cx="8" cy="8" r="3" />
    <path d="M8 1.5v1.5M8 13v1.5M1.5 8h1.5M13 8h1.5M3.3 3.3l1 1M11.7 11.7l1 1M12.7 3.3l-1 1M3.3 12.7l1-1" />
  </Icon>
);
export const IcMoon = (p: Props) => (
  <Icon {...p}>
    <path d="M13 9a5 5 0 0 1-6-6 5 5 0 1 0 6 6z" />
  </Icon>
);
export const IcSettings = (p: Props) => (
  <Icon {...p}>
    <circle cx="8" cy="8" r="1.8" />
    <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.3 3.3l1.5 1.5M11.2 11.2l1.5 1.5M12.7 3.3l-1.5 1.5M4.8 11.2l-1.5 1.5" />
  </Icon>
);
export const IcUpload = (p: Props) => (
  <Icon {...p} d="M8 11V3m0 0L5 6m3-3l3 3M3 13h10" />
);
export const IcCheck = (p: Props) => <Icon {...p} d="M3 8.5L6.5 12 13 5" />;
export const IcClose = (p: Props) => <Icon {...p} d="M4 4l8 8M12 4l-8 8" />;
export const IcLock = (p: Props) => (
  <Icon {...p}>
    <path d="M4.5 7.5h7v6h-7v-6zM6 7.5V5a2 2 0 0 1 4 0v2.5" />
    <circle cx="8" cy="10.5" r="0.7" fill="currentColor" stroke="none" />
  </Icon>
);
export const IcUnlock = (p: Props) => (
  <Icon {...p}>
    <path d="M4.5 7.5h7v6h-7v-6zM6 7.5V5a2 2 0 0 1 3.8-.8" />
  </Icon>
);
export const IcBookmark = (p: Props) => (
  <Icon {...p}>
    <path d="M4 2.5h8v11l-4-2.5-4 2.5v-11z" />
  </Icon>
);
export const IcDot = (p: Props) => (
  <Icon {...p}>
    <circle cx="8" cy="8" r="3" fill="currentColor" stroke="none" />
  </Icon>
);
export const IcChat = (p: Props) => (
  <Icon {...p}>
    <path d="M3 4a1.5 1.5 0 0 1 1.5-1.5h7A1.5 1.5 0 0 1 13 4v5a1.5 1.5 0 0 1-1.5 1.5H7l-3 3v-3h-1A1.5 1.5 0 0 1 3 9V4z" />
  </Icon>
);
export const IcArrowL = (p: Props) => <Icon {...p} d="M12.5 8h-9m3-3l-3 3 3 3" />;
export const IcArrowR = (p: Props) => <Icon {...p} d="M3.5 8h9m-3-3l3 3-3 3" />;
export const IcSend = (p: Props) => (
  <Icon {...p} d="M13.5 2.5L2.5 7l5 1.5L9 13.5l4.5-11z" />
);
export const IcEdit = (p: Props) => (
  <Icon {...p} d="M11.5 2.5l2 2-7.5 7.5H4V10l7.5-7.5zM10 4l2 2" />
);
export const IcPrivate = (p: Props) => (
  <Icon {...p} d="M4.5 7.5h7v6h-7v-6zM6 7.5V5a2 2 0 0 1 4 0v2.5" />
);
export const IcExpand = (p: Props) => (
  <Icon {...p} d="M9 3h4v4M7 13H3V9M13 3l-5 5M3 13l5-5" />
);
export const IcHighlight = (p: Props) => (
  <Icon {...p} d="M3 13h10M4.5 10.5l3 3 6-6-3-3-6 6z" />
);
export const IcSpark = (p: Props) => (
  <Icon {...p} d="M8 2v3M8 11v3M2 8h3M11 8h3M4 4l2 2M10 10l2 2M12 4l-2 2M4 12l2-2" />
);
export const IcChevron = (p: Props) => <Icon {...p} d="M4 6l4 4 4-4" />;
