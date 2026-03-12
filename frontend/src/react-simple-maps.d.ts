declare module "react-simple-maps" {
  import React, { ReactNode, CSSProperties } from "react";

  export interface Geography {
    rsmKey: string;
    properties: Record<string, string>;
    [key: string]: unknown;
  }

  export interface GeographiesChildrenProps {
    geographies: Geography[];
  }

  export function ComposableMap(props: {
    projectionConfig?: Record<string, unknown>;
    style?: CSSProperties;
    children?: ReactNode;
    [key: string]: unknown;
  }): JSX.Element;

  export function Geographies(props: {
    geography: string;
    children: (props: GeographiesChildrenProps) => ReactNode;
  }): JSX.Element;

  export function Geography(props: {
    key?: string;
    geography: Geography;
    fill?: string;
    stroke?: string;
    strokeWidth?: number;
    style?: { default?: CSSProperties; hover?: CSSProperties; pressed?: CSSProperties };
    onMouseEnter?: (e: React.MouseEvent) => void;
    onMouseMove?: (e: React.MouseEvent) => void;
    onMouseLeave?: (e: React.MouseEvent) => void;
  }): JSX.Element;
}
