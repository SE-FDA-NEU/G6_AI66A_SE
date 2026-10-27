import { Folder, FileText, LayoutGrid, Inbox, Search, Upload, ChevronRight } from 'lucide-react';
const icons = { folder: Folder, file: FileText, grid: LayoutGrid, inbox: Inbox, search: Search, upload: Upload, chevron: ChevronRight };
export default function WorkspaceIcon({ name = 'file', size = 22, ...props }) {
  const Icon = icons[name] || FileText;
  return <Icon size={size} strokeWidth={1.5} aria-hidden="true" {...props} />;
}
