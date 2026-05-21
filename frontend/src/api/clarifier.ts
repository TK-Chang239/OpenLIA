export interface ClarifyingQuestion {
  id: string;
  text: string;
  kind: "multiple_choice" | "free_text";
  options?: string[];
}

export interface CapabilityWarning {
  capability_id: string;
  detected_phrase: string;
  user_message: string;
  available_actions: ("proceed_without" | "cancel_and_edit" | "clarify")[];
}

export interface ClarifierOutput {
  questions: ClarifyingQuestion[];
  blocking_warnings: CapabilityWarning[];
  notices: string[];
  detected_intents: string[];
}
