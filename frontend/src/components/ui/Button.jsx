import * as React from "react";
import { cn } from "../../lib/utils";

const Button = React.forwardRef(({ className, variant = "default", size = "default", asChild = false, ...props }, ref) => {
  const Comp = asChild ? "span" : "button";
  
  const variants = {
    default: "bg-[#44D62C] hover:bg-[#3BC424] text-[#FFFFFF] font-semibold",
    outline: "border-2 border-[#44D62C] bg-[#FFFFFF] hover:bg-green-50 text-[#44D62C] font-semibold",
    ghost: "hover:bg-green-50 text-[#313131]",
    link: "text-[#44D62C] underline-offset-4 hover:underline font-medium",
  };
  
  const sizes = {
    default: "h-11 px-6 py-3",
    sm: "h-9 px-4 py-2",
    lg: "h-12 px-8 py-3",
    icon: "h-10 w-10",
  };
  
  return (
    <Comp
      className={cn(
        "inline-flex items-center justify-center rounded-xl text-sm transition-all duration-200 shadow-md hover:shadow-lg disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Button.displayName = "Button";

export { Button };
