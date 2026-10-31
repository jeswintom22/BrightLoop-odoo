import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
  {
    variants: {
      variant: {
        default: "border-transparent bg-ink text-cream-card",
        secondary: "border-transparent bg-sage-faint text-ink-muted",
        success: "border-transparent bg-success/15 text-success",
        warning: "border-transparent bg-warning/15 text-warning",
        destructive: "border-transparent bg-danger/15 text-danger",
        outline: "border-line text-ink-muted",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

const STATUS_VARIANT: Record<string, BadgeProps["variant"]> = {
  draft: "secondary",
  sent: "warning",
  confirmed: "warning",
  active: "success",
  paid: "success",
  cancelled: "outline",
  closed: "outline",
  paused: "warning",
  expired: "destructive",
  posted: "success",
  voided: "destructive",
  success: "success",
  partial: "warning",
  failed: "destructive",
  running: "secondary",
  converted: "success",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{status}</Badge>;
}
