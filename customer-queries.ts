//submit new incident
export async function createIncident(payload: {
  reporter_id: string;
  service_id: string;
  category: string;
  description: string;
  impact: 'Low' | 'Medium' | 'High';
  urgency: 'Low' | 'Medium' | 'High';
  affected_users_count: number;
  priority: 'P1' | 'P2' | 'P3' | 'P4';
}) {
  const { data, error } = await supabase
    .from('incidents')
    .insert([
      {
        ...payload,
        status: 'NEW',
      },
    ])
    .select()
    .single();

  if (error) throw error;
  return data;
}