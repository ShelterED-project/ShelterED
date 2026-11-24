import { usePendingEntry } from "@/features/teacher/pendingCreates";
import { save } from "./content";

/** Позначка біля елемента, який ще не створено на сервері: чекає мережі або відхилений. */
export default function PendingMark({ id }: { id: string }) {
  const entry = usePendingEntry(id);
  if (!entry) return null;
  if (entry.error)
    return (
      <p role="alert" className="text-sm font-semibold text-accent">
        {entry.error}
      </p>
    );
  return <p className="text-xs text-dim">{save.pendingCreate}</p>;
}
