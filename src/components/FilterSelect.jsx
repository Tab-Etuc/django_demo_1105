import React from "react";
import { Select } from "radix-ui";
import { Check, ChevronDown, ChevronUp } from "lucide-react";

export function FilterSelect({ value, onChange, children, "aria-label": label }) {
  const options = React.Children.toArray(children).flatMap(child =>
    child.type === React.Fragment ? React.Children.toArray(child.props.children) : [child]);
  return (
    <Select.Root value={String(value)} onValueChange={value => onChange({ target: { value } })}>
      <Select.Trigger className="filter-select-trigger" aria-label={label}>
        <Select.Value /><Select.Icon><ChevronDown size={16} /></Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content className="filter-select-menu" position="popper" sideOffset={6} collisionPadding={12}>
          <Select.ScrollUpButton className="filter-select-scroll"><ChevronUp size={16} /></Select.ScrollUpButton>
          <Select.Viewport><Select.Group>
            <Select.Label className="filter-select-label">{label}</Select.Label>
            {options.map(option => (
              <Select.Item className="filter-select-option" key={option.props.value} value={String(option.props.value)}>
                <Select.ItemText>{option.props.children}</Select.ItemText>
                <Select.ItemIndicator><Check size={16} /></Select.ItemIndicator>
              </Select.Item>
            ))}
          </Select.Group></Select.Viewport>
          <Select.ScrollDownButton className="filter-select-scroll"><ChevronDown size={16} /></Select.ScrollDownButton>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
