!start.

+!start : .my_name(N) <-
    +my_name(N).

// === OUT OF ZONE RECOVERY ===

+step(_) : pos(Q,R,S) & .dist_to_origin(Q,R,S,D) & D > 30 <-
    .path_to_origin(Dir);
    .print("pos:", Q, R, S, "| Out of zone (dist:", D, "), returning:", Dir);
    -cnp_state(_);
    -move_task(_,_,_,_,_);
    -relay_task(_,_,_,_,_);
    -send_task(_,_,_,_);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(Dir).

// === SCHEDULED DATA TRANSFER ===

+step(Step) : send_task(_,_,_,ExecStep) & Step > ExecStep + 10 <-
    -send_task(_,_,_,ExecStep);
    -cnp_state(_);
    .skip.

+step(Step) : send_task(TQ,TR,TS,ExecStep) & Step >= ExecStep
    & pos(Q,R,S) & .hex_dist(Q,R,S,TQ,TR,TS,Hop) & Hop <= 4
    & my_name(Me) <-
    .print("CNP:", Me, "sending scheduled data to", TQ, TR, TS);
    -send_task(TQ,TR,TS,ExecStep);
    -cnp_state(_);
    .send(TQ, TR, TS).

+step(Step) : send_task(TQ,TR,TS,ExecStep) & Step >= ExecStep
    & pos(Q,R,S) & .hex_dist(Q,R,S,TQ,TR,TS,Hop) & Hop > 4 <-
    .path_to_pos(TQ,TR,TS,D);
    .print("pos:", Q, R, S, "| Moving toward send target:", TQ, TR, TS, "via", D);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(_,_,_,_,ExecStep) & Step > ExecStep + 40 <-
    .print("CNP: relay task expired");
    -relay_task(_,_,_,_,ExecStep);
    -move_task(_,_,_,_,ExecStep);
    -cnp_state(_);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    .skip.

+step(Step) : relay_task(Manager,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & pos(Q,R,S) & .hex_dist(Q,R,S,TQ,TR,TS,Hop) & Hop <= 30
    & my_name(Me) <-
    .print("CNP:", Me, "relaying for", Manager, "to", TQ, TR, TS);
    -relay_task(Manager,TQ,TR,TS,ExecStep);
    -move_task(Manager,_,_,_,ExecStep);
    -cnp_state(_);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    .relay(TQ, TR, TS, 50).

+step(Step) : relay_task(Manager,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & move_task(Manager,MQ,MR,MS,ExecStep)
    & pos(Q,R,S) & pprev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Oscillating to relay target:", MQ, MR, MS, "escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(Manager,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & move_task(Manager,MQ,MR,MS,ExecStep)
    & pos(Q,R,S) & prev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Stuck at relay target:", MQ, MR, MS, "escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(Q,R,S);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(Manager,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & move_task(Manager,MQ,MR,MS,ExecStep)
    & pos(Q,R,S) & .hex_dist(Q,R,S,TQ,TR,TS,Hop) & Hop > 30
    & prev_pos(PQ,PR,PS) <-
    .path_to_pos(MQ,MR,MS,D);
    .print("pos:", Q, R, S, "| Late for relay target:", MQ, MR, MS, "via", D);
    -pprev_pos(_,_,_);
    +pprev_pos(PQ,PR,PS);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(Manager,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & move_task(Manager,MQ,MR,MS,ExecStep)
    & pos(Q,R,S) & .hex_dist(Q,R,S,TQ,TR,TS,Hop) & Hop > 30 <-
    .path_to_pos(MQ,MR,MS,D);
    .print("pos:", Q, R, S, "| Late for relay target:", MQ, MR, MS, "via", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(_,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & pos(Q,R,S) & pprev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Oscillating closing relay range:", TQ, TR, TS, "escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(_,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & pos(Q,R,S) & prev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Stuck closing relay range:", TQ, TR, TS, "escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(Q,R,S);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(_,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & pos(Q,R,S) & .hex_dist(Q,R,S,TQ,TR,TS,Hop) & Hop > 30
    & prev_pos(PQ,PR,PS) <-
    .path_to_pos(TQ,TR,TS,D);
    .print("pos:", Q, R, S, "| Closing relay range:", TQ, TR, TS, "via", D);
    -pprev_pos(_,_,_);
    +pprev_pos(PQ,PR,PS);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(_,TQ,TR,TS,ExecStep) & Step >= ExecStep
    & pos(Q,R,S) & .hex_dist(Q,R,S,TQ,TR,TS,Hop) & Hop > 30 <-
    .path_to_pos(TQ,TR,TS,D);
    .print("pos:", Q, R, S, "| Closing relay range:", TQ, TR, TS, "via", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : relay_task(_,_,_,_,ExecStep) & Step < ExecStep
    & not move_task(_,_,_,_,ExecStep) <-
    .skip.

+step(Step) : move_task(Manager,_,_,_,ExecStep) & Step > ExecStep + 40 <-
    .print("CNP: relay positioning expired for", Manager);
    -move_task(Manager,_,_,_,ExecStep);
    -cnp_state(_);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    .skip.

+step(Step) : move_task(_,TQ,TR,TS,ExecStep) & Step <= ExecStep + 40 & pos(TQ,TR,TS) <-
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    .skip.

+step(Step) : move_task(_,TQ,TR,TS,ExecStep) & Step <= ExecStep + 40
    & pos(Q,R,S) & pprev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Oscillating to relay target:", TQ, TR, TS, "escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : move_task(_,TQ,TR,TS,ExecStep) & Step <= ExecStep + 40
    & pos(Q,R,S) & prev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Stuck at relay target:", TQ, TR, TS, "escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(Q,R,S);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : move_task(_,TQ,TR,TS,ExecStep) & Step <= ExecStep + 40
    & pos(Q,R,S) & prev_pos(PQ,PR,PS) <-
    .path_to_pos(TQ,TR,TS,D);
    .print("pos:", Q, R, S, "| Moving to relay target:", TQ, TR, TS, "via", D);
    -pprev_pos(_,_,_);
    +pprev_pos(PQ,PR,PS);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : move_task(_,TQ,TR,TS,ExecStep) & Step <= ExecStep + 40 & pos(Q,R,S) <-
    .path_to_pos(TQ,TR,TS,D);
    .print("pos:", Q, R, S, "| Moving to relay target:", TQ, TR, TS, "via", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(Step) : cnp_state(committed(ExecStep)) & Step < ExecStep <-
    .skip.

+step(Step) : cnp_state(committed(ExecStep)) & Step > ExecStep + 40 <-
    -cnp_state(committed(ExecStep));
    .skip.

// === RECHARGE ===

+step(_) : energy(E) & E < 30 & .at_oasis & pos(Q,R,S) <-
    .print("pos:", Q, R, S, "| Recharging");
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    .recharge.

+step(_) : energy(E) & E < 30 & pprev_pos(Q,R,S) & pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Oscillating to oasis, escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : energy(E) & E < 30 & pos(Q,R,S) & prev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Stuck going to oasis, escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(Q,R,S);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : energy(E) & E < 30 & prev_pos(PQ,PR,PS) & pos(Q,R,S) <-
    .path_to_oasis(D);
    .print("pos:", Q, R, S, "| Low energy, heading to oasis:", D);
    -pprev_pos(_,_,_);
    +pprev_pos(PQ,PR,PS);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : energy(E) & E < 30 & pos(Q,R,S) <-
    .path_to_oasis(D);
    .print("pos:", Q, R, S, "| Low energy, heading to oasis:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

// === CNP CONTRACTOR ===

+cfp(Manager,DQ,DR,DS,CfpStep) : pos(Q,R,S)
    & .dist_to_origin(DQ,DR,DS,DataDist)
    & .dist_to_origin(Q,R,S,MyDist)
    & MyDist < DataDist
    & energy(E) & E > 30
    & my_name(Me) & not cnp_state(_) <-
    .print("CNP:", Me, "bidding for", Manager, "from", Q, R, S);
    +cnp_state(bidding(Manager,CfpStep));
    .broadcast(tell, bid(Me, Manager, Q, R, S, CfpStep, E)).

+step(Step) : cnp_state(bidding(_,CfpStep)) & Step > CfpStep + 4 <-
    .print("CNP: bid expired");
    -cnp_state(_);
    .skip.

+step(_) : cnp_state(bidding(_,_)) <-
    .skip.

// === CNP MANAGER ===

+step(Step) : cnp_retry_after(Retry) & Step >= Retry <-
    -cnp_retry_after(Retry);
    .skip.

+step(Step) : pos(Q,R,S) & data(_, pos(Q,R,S))
    & .dist_to_origin(Q,R,S,D) & D > 4 & D <= 30
    & energy(E) & E > 20
    & not cnp_state(_) & not cnp_retry_after(_) & my_name(Me) <-
    .print("CNP:", Me, "announcing CFP at", Q, R, S, "dist:", D);
    .broadcast(tell, cfp(Me, Q, R, S, Step));
    +cnp_state(announcing(Step));
    +cnp_data_pos(Q, R, S);
    .skip.

+step(Step) : cnp_state(announcing(CfpStep)) & Step <= CfpStep + 1 <-
    .skip.

+step(Step) : cnp_state(announcing(CfpStep)) & cnp_data_pos(DQ, DR, DS) & Step > CfpStep + 1 & my_name(Me) <-
    .cnp_prepare_route(Me, DQ, DR, DS, Step, Status);
    .print("CNP:", Me, "route status:", Status, "for data at", DQ, DR, DS);
    -cnp_state(announcing(CfpStep));
    -cnp_data_pos(DQ, DR, DS);
    .skip.

// === DIRECT SEND ===

+step(_) : pos(Q,R,S) & data(Packets, pos(Q,R,S))
    & .dist_to_origin(Q,R,S,D) & D <= 4
    & energy(E) & E > 15 <-
    .print("Sending data from pos:", Q, R, S, "| packets:", Packets, "| energy:", E);
    .send(0, 0, 0).

// === NORMAL DATA COLLECTION ===

+step(_) : data(_, _) & .should_pursue_data & pos(Q,R,S) & pprev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Oscillating toward data, escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : data(_, _) & .should_pursue_data & pos(Q,R,S) & prev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Stuck toward data, escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(Q,R,S);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : data(_, _) & .should_pursue_data & pos(Q,R,S) & prev_pos(PQ,PR,PS) <-
    .path_to_data(D);
    .print("pos:", Q, R, S, "| Moving toward data:", D);
    -pprev_pos(_,_,_);
    +pprev_pos(PQ,PR,PS);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : data(_, _) & .should_pursue_data & pos(Q,R,S) <-
    .path_to_data(D);
    .print("pos:", Q, R, S, "| Moving toward data:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

// === PATROL AGENT (agentA1 stays near origin to collect breach data) ===

+step(_) : .should_patrol_origin & pos(Q,R,S) & .dist_to_origin(Q,R,S,D) & D > 8 <-
    .path_to_origin(Dir);
    .print("pos:", Q, R, S, "| Patrol agent returning to base zone");
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(Dir).

+step(_) : .should_patrol_origin & pos(Q,R,S) & prev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Patrol agent stuck near origin, escape:", D);
    -pprev_pos(_,_,_);
    -prev_pos(Q,R,S);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : .should_patrol_origin & pos(Q,R,S) <-
    .explore_near_origin(D);
    .print("pos:", Q, R, S, "| Patrol agent near origin:", D);
    -pprev_pos(_,_,_);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).

// === EXPLORATION ===

+step(_) : pos(Q,R,S) & prev_pos(Q,R,S) <-
    .safe_escape_direction(D);
    .print("pos:", Q, R, S, "| Stuck exploring, random escape:", D);
    -prev_pos(Q,R,S);
    +prev_pos(Q,R,S);
    .move(D).

+step(_) : pos(Q,R,S) <-
    .explore_direction(D);
    .print("pos:", Q, R, S, "| Exploring:", D);
    -prev_pos(_,_,_);
    +prev_pos(Q,R,S);
    .move(D).
