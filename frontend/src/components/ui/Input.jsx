import * as React from "react";
import { cn } from "../../lib/utils";

const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-11 w-full rounded-xl border-2 border-gray-200 bg-[#FFFFFF] px-4 py-3 text-sm text-[#313131] file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-400 focus:ring-2 focus:ring-[#44D62C] focus:border-[#44D62C] disabled:cursor-not-allowed disabled:opacity-50 transition-all duration-200",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
