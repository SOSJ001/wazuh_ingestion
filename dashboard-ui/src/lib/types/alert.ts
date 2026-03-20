export interface Alert {
	id: string;
	timestamp: string;
	agent_name: string;
	agent_id: string;
	rule_level: number;
	rule_description: string;
	rule_id: string;
	full_log: string;
	log_hmac?: string | null;
	hmac_algo?: string | null;
	integrity_status?: 'valid' | 'invalid' | 'missing';
	integrity_checked_at?: string;
	verified_by?: string | null;
	verified_at?: string | null;
	is_verified: number;
	created_at: string;
}
