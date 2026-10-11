import {
  Briefcase,
  BookOpenText,
  Heart,
  Leaf,
  PersonSimpleRun,
  SunHorizon,
  UsersThree,
  Wallet,
  type Icon,
} from "@phosphor-icons/react";

const ICONS: Record<string, Icon> = {
  emotional: Heart,
  environmental: Leaf,
  financial: Wallet,
  intellectual: BookOpenText,
  occupational: Briefcase,
  physical: PersonSimpleRun,
  social: UsersThree,
  spiritual: SunHorizon,
};

export function DimensionIcon({ dimension, size = 20, className = "" }: { dimension: string; size?: number; className?: string }) {
  const I = ICONS[dimension] ?? Heart;
  return <I size={size} className={className} aria-hidden />;
}
