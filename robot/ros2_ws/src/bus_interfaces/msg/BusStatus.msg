# Periodic bus status for the dispatcher / dashboard.
string bus_id
string state                 # "idle" | "navigating" | "error"
string current_stop          # last stop reached ("" if unknown)
string target_stop           # "" when idle
float32 distance_remaining_m # 0 when idle
