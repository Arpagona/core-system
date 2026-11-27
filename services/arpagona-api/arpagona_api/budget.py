"""Garde d'admission, pas une limite de facturation du fournisseur.

Réservations et consommation en micro-USD arrondis vers le haut, dans la base
métier existante. Une ambiguïté ne libère jamais automatiquement une réserve.
"""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

SCALE = 1_000_000


def micros(value, positive=False, ceiling=True):
    if isinstance(value, bool) or value is None:
        raise ValueError('montant invalide')
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d < 0 or (positive and d == 0):
            raise ValueError('montant invalide')
        n = int((d*SCALE).to_integral_value(rounding=ROUND_CEILING if ceiling else ROUND_FLOOR))
        if positive and n == 0:
            raise ValueError('montant inférieur au micro-USD')
        if n > 2**62:
            raise ValueError('montant hors limite')
        return n
    except (InvalidOperation, TypeError, OverflowError) as exc:
        raise ValueError('montant invalide') from exc


def measured_cost(value):
    try:
        return micros(value)/SCALE
    except ValueError:
        return None


class BudgetLedger:
    def __init__(self, db, lock):
        self.db, self.lock = db, lock
        db.execute('''CREATE TABLE IF NOT EXISTS budget_entries (
            key TEXT PRIMARY KEY, user_id INTEGER NOT NULL, run_id TEXT,
            created_at REAL NOT NULL, settled_at REAL,
            reserved_micros INTEGER NOT NULL CHECK(reserved_micros>0),
            actual_micros INTEGER CHECK(actual_micros>=0),
            state TEXT NOT NULL CHECK(state IN ('reserved','settled','unknown'))
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS budget_run ON budget_entries(run_id)')

    def _summary(self, now):
        spent, reserved, unknown = 0, 0, 0
        for r in self.db.execute('SELECT * FROM budget_entries'):
            if r['state'] == 'settled':
                if r['settled_at'] >= now-86400:
                    spent += r['actual_micros']
            else:
                reserved += r['reserved_micros']
                unknown += int(r['state'] == 'unknown')
        # Migration prudente : ne jamais effacer le coût des exécutions historiques.
        for r in self.db.execute('''SELECT m.* FROM missions m LEFT JOIN budget_entries b
                                    ON (m.run_id=b.run_id AND m.user_id=b.user_id)
                                    OR b.key=('legacy-mission-'||m.id||'-'||m.user_id) WHERE b.key IS NULL'''):
            cost = measured_cost(r['cost_usd'])
            if r['status'] == 'en_cours' or cost is None:
                unknown += 1
            elif (r['ended_at'] or r['created_at']) >= now-86400:
                spent += micros(cost)
        return spent, reserved, unknown

    def legacy_unknown(self):
        with self.lock:
            rows = self.db.execute("""SELECT m.* FROM missions m LEFT JOIN budget_entries b
                ON (m.run_id=b.run_id AND m.user_id=b.user_id)
                OR b.key=('legacy-mission-'||m.id||'-'||m.user_id) WHERE b.key IS NULL""").fetchall()
            return [{'key':f"legacy-mission-{r['id']}-{r['user_id']}", 'mission':r['id'],
                     'statut':r['status'], 'user_id':r['user_id']}
                    for r in rows if measured_cost(r['cost_usd']) is None]

    def snapshot(self, now):
        with self.lock:
            spent, reserved, unknown = self._summary(now)
            return {'mesure_usd': spent/SCALE, 'reserve_usd': reserved/SCALE,
                    'couts_inconnus': unknown, 'plafond_fournisseur_garanti': False}

    def reserve(self, key, user_id, amount, day_limit, now):
        reserve, limit = micros(amount, True), micros(day_limit, True, ceiling=False)
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                if self.db.execute('SELECT 1 FROM budget_entries WHERE key=?', (key,)).fetchone():
                    return 'existant'
                spent, reserved, unknown = self._summary(now)
                if unknown:
                    return 'inconnu'
                if spent+reserved+reserve > limit:
                    return 'limite'
                self.db.execute('''INSERT INTO budget_entries
                    (key,user_id,created_at,reserved_micros,state) VALUES (?,?,?,?,'reserved')''',
                    (key,user_id,now,reserve))
                self.db.execute('COMMIT')
                return 'ok'
            finally:
                if self.db.in_transaction:
                    self.db.execute('ROLLBACK')

    def bind(self, key, run_id):
        with self.lock:
            self.db.execute("UPDATE budget_entries SET run_id=? WHERE key=? AND run_id IS NULL AND state='reserved'",
                            (run_id,key))

    def settle(self, key, cost, now):
        actual = measured_cost(cost)
        with self.lock:
            self.db.execute('''UPDATE budget_entries SET actual_micros=?,settled_at=?,state=?
                WHERE key=? AND state='reserved' ''',
                (micros(actual) if actual is not None else None, now,
                 'settled' if actual is not None else 'unknown', key))

    def reconcile_unknown(self, key, cost, evidence, operator_id, now):
        """Geste opérateur explicite après preuve de fin/non-démarrage ; jamais automatique."""
        actual = micros(cost)
        if not isinstance(evidence, str) or len(evidence.strip()) < 12 or len(evidence) > 400:
            raise ValueError('preuve de rapprochement obligatoire (12 à 400 caractères)')
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                operator = self.db.execute('SELECT role FROM users WHERE id=?', (operator_id,)).fetchone()
                if not operator or operator['role'] != 'admin':
                    raise PermissionError('rapprochement réservé à un administrateur')
                # Rapprochement d'une ancienne mission sans écriture budgétaire :
                # réservé au geste opérateur, jamais à l'admission automatique.
                legacy = self.db.execute("SELECT * FROM missions WHERE ('legacy-mission-'||id||'-'||user_id)=? AND status!='en_cours'", (key,)).fetchone()
                if legacy and measured_cost(legacy['cost_usd']) is None:
                    self.db.execute("INSERT OR IGNORE INTO budget_entries(key,user_id,run_id,created_at,reserved_micros,state) VALUES(?,?,?,?,1,'unknown')",
                                    (key,legacy['user_id'],legacy['run_id'],legacy['created_at']))
                changed = self.db.execute("UPDATE budget_entries SET actual_micros=?,settled_at=?,state='settled' WHERE key=? AND state IN ('unknown','reserved')",
                                          (actual,now,key)).rowcount
                if changed != 1:
                    raise ValueError('réservation inconnue ou non rapprochable')
                if legacy:
                    self.db.execute('UPDATE missions SET cost_usd=? WHERE id=?', (actual/SCALE,legacy['id']))
                self.db.execute('INSERT INTO audit(ts,user_id,action,detail) VALUES(?,?,?,?)',
                    (now,operator_id,'budget_rapproche',f'{key} coût={actual/SCALE} USD preuve={evidence.strip()}'))
                self.db.execute('COMMIT')
            finally:
                if self.db.in_transaction:
                    self.db.execute('ROLLBACK')

    def settle_run(self, run_id, cost, now):
        with self.lock:
            row = self.db.execute('SELECT key FROM budget_entries WHERE run_id=?', (run_id,)).fetchone()
        if row:
            self.settle(row['key'],cost,now)
