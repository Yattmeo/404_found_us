import * as React from "react";
import { cn } from "../../lib/utils";

const Tabs = ({ value, onValueChange, children, className }) => {
  return (
    <div className={cn("w-full", className)}>
      {React.Children.map(children, child =>
        React.cloneElement(child, { currentValue: value, onValueChange })
      )}
    </div>
  );
};

const TabsList = ({ className, children, currentValue, onValueChange }) => {
  return (
    <div
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-lg bg-gray-100 p-1 text-gray-500 w-full",
        className
      )}
    >
      {React.Children.map(children, child =>
        React.cloneElement(child, { currentValue, onValueChange })
      )}
    </div>
  );
};

const TabsTrigger = ({ className, value, children, currentValue, onValueChange }) => {
  const isActive = currentValue === value;
  
  return (
    <button
      type="button"
      onClick={() => onValueChange(value)}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ring-offset-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#44D62C] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 flex-1",
        isActive ? "bg-white text-gray-900 shadow-sm" : "hover:bg-gray-50",
        className
      )}
    >
      {children}
    </button>
  );
};

const TabsContent = ({ className, value, children, currentValue }) => {
  if (currentValue !== value) return null;
  
  return (
    <div
      className={cn(
        "mt-4 ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2",
        className
      )}
    >
      {children}
    </div>
  );
};

export { Tabs, TabsList, TabsTrigger, TabsContent };
