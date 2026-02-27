export interface Alert {
	id: string;
	timestamp: string;
	agent_name: string;
	agent_id: string;
	rule_level: number;
	rule_description: string;
	rule_id: string;
	full_log: string;
	is_verified: number;
	created_at: string;
}
