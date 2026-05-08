"""
Servizi (business logic) per il dominio Partita.

I servizi orchestrano l'accesso ai modelli ORM e applicano regole di
business. Sono chiamati dai router e ritornano modelli ORM o sollevano
eccezioni di dominio.

Convenzione: ogni metodo è async, accetta `AsyncSession` come primo
argomento dopo self, e ritorna il modello ORM (o None / lista).
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelli import (
    EventoGrezzo,
    EventoValidato,
    GiocatorePartita,
    Partita,
    StatoReview,
)
from app.schemi import (
    EventoGrezzoAggiornamento,
    EventoGrezzoCreazione,
    EventoValidatoAggiornamento,
    EventoValidatoCreazione,
    PartitaAggiornamento,
    PartitaCreazione,
)

# === Eccezioni dominio ===


class PartitaInesistenteError(Exception):
    """La partita richiesta non esiste."""


class EventoInesistenteError(Exception):
    """L'evento richiesto non esiste."""


class StatoReviewIncompatibileError(Exception):
    """L'azione non è ammessa nello stato di review corrente."""


class ColoriDuplicatiError(Exception):
    """Più giocatori configurati con lo stesso colore."""


class OrdineSedutaInvalidoError(Exception):
    """Ordini di seduta duplicati o non consecutivi a partire da 1."""


# === Servizio Partita ===


class ServizioPartita:
    """Operazioni sul ciclo di vita delle partite."""

    @staticmethod
    async def crea(
        db: AsyncSession, dati: PartitaCreazione
    ) -> Partita:
        """
        Crea una nuova partita con i suoi giocatori.

        Validazioni:
        - I colori dei giocatori devono essere tutti distinti.
        - Gli ordini di seduta devono essere consecutivi 1..N e distinti.
        """
        ServizioPartita._valida_giocatori(dati)

        partita = Partita(
            data_inizio=dati.data_inizio,
            luogo=dati.luogo,
            note=dati.note,
            stato_review=StatoReview.GREZZA,
        )

        for g_dati in dati.giocatori:
            partita.giocatori.append(
                GiocatorePartita(
                    nome=g_dati.nome,
                    colore=g_dati.colore,
                    ordine_seduta=g_dati.ordine_seduta,
                )
            )

        db.add(partita)
        await db.flush()
        await db.commit()
        await db.refresh(partita, ["giocatori", "video"])
        return partita

    @staticmethod
    def _valida_giocatori(dati: PartitaCreazione) -> None:
        """Verifica unicità colori e ordini di seduta."""
        colori = [g.colore for g in dati.giocatori]
        if len(colori) != len(set(colori)):
            raise ColoriDuplicatiError(
                f"Colori duplicati nella partita: {colori}"
            )

        ordini = sorted(g.ordine_seduta for g in dati.giocatori)
        atteso = list(range(1, len(dati.giocatori) + 1))
        if ordini != atteso:
            raise OrdineSedutaInvalidoError(
                f"Ordine seduta deve essere 1..{len(dati.giocatori)} senza duplicati, "
                f"ricevuto {ordini}"
            )

    @staticmethod
    async def lista(
        db: AsyncSession,
        offset: int = 0,
        limite: int = 50,
        stato: StatoReview | None = None,
    ) -> Sequence[Partita]:
        """Lista partite paginata, ordinata per data_inizio decrescente."""
        stmt = select(Partita).order_by(Partita.data_inizio.desc())

        if stato is not None:
            stmt = stmt.where(Partita.stato_review == stato)

        stmt = stmt.offset(offset).limit(limite)
        risultato = await db.execute(stmt)
        return risultato.scalars().all()

    @staticmethod
    async def trova_per_id(db: AsyncSession, partita_id: str) -> Partita:
        """Carica una partita con giocatori e video."""
        stmt = (
            select(Partita)
            .where(Partita.id == partita_id)
            .options(
                selectinload(Partita.giocatori),
                selectinload(Partita.video),
            )
        )
        risultato = await db.execute(stmt)
        try:
            return risultato.scalar_one()
        except NoResultFound as e:
            raise PartitaInesistenteError(
                f"Partita '{partita_id}' non trovata"
            ) from e

    @staticmethod
    async def aggiorna(
        db: AsyncSession,
        partita_id: str,
        dati: PartitaAggiornamento,
    ) -> Partita:
        """Aggiorna i metadata di una partita esistente."""
        partita = await ServizioPartita.trova_per_id(db, partita_id)

        for campo, valore in dati.model_dump(exclude_unset=True).items():
            setattr(partita, campo, valore)

        await db.commit()
        # Refresh completo: i campi onupdate (data_aggiornamento) e le
        # relazioni vanno ricaricati dal DB dopo il commit.
        await db.refresh(partita)
        await db.refresh(partita, ["giocatori", "video"])
        return partita

    @staticmethod
    async def elimina(
        db: AsyncSession,
        partita_id: str,
        servizio_video: object | None = None,
    ) -> None:
        """
        Elimina una partita e tutto il contenuto associato.

        Args:
            servizio_video: opzionale `ServizioVideo` per cleanup file.
                            Se None, i record DB sono eliminati ma i file
                            video restano sul disco (deprecato per produzione).
        """
        partita = await ServizioPartita.trova_per_id(db, partita_id)

        # Cleanup file video prima del CASCADE DB
        if servizio_video is not None:
            # Lazy import per evitare import circolare
            from app.servizi.video_servizio import ServizioVideo

            if isinstance(servizio_video, ServizioVideo):
                await servizio_video.elimina_tutti_di_partita(db, partita_id)

        await db.delete(partita)
        await db.commit()


# === Servizio Eventi Grezzi ===


class ServizioEventiGrezzi:
    """Gestione eventi grezzi (osservazioni non validate)."""

    @staticmethod
    async def aggiungi(
        db: AsyncSession,
        partita_id: str,
        dati: EventoGrezzoCreazione,
    ) -> EventoGrezzo:
        """Aggiunge un evento grezzo a una partita esistente."""
        # Verifica che la partita esista (solleva PartitaInesistenteError se no)
        await ServizioPartita.trova_per_id(db, partita_id)

        evento = EventoGrezzo(
            partita_id=partita_id,
            ts_evento=dati.ts_evento,
            tipo=dati.tipo,
            fonte=dati.fonte,
            confidenza=dati.confidenza,
            dati=dict(dati.dati),
            validato=False,
        )
        db.add(evento)
        await db.commit()
        await db.refresh(evento)
        return evento

    @staticmethod
    async def aggiungi_batch(
        db: AsyncSession,
        partita_id: str,
        eventi: list[EventoGrezzoCreazione],
    ) -> list[EventoGrezzo]:
        """Aggiunge più eventi in batch (tipico upload da tablet)."""
        await ServizioPartita.trova_per_id(db, partita_id)

        oggetti = [
            EventoGrezzo(
                partita_id=partita_id,
                ts_evento=e.ts_evento,
                tipo=e.tipo,
                fonte=e.fonte,
                confidenza=e.confidenza,
                dati=dict(e.dati),
                validato=False,
            )
            for e in eventi
        ]
        db.add_all(oggetti)
        await db.commit()
        for o in oggetti:
            await db.refresh(o)
        return oggetti

    @staticmethod
    async def lista(
        db: AsyncSession,
        partita_id: str,
        solo_non_validati: bool = False,
    ) -> Sequence[EventoGrezzo]:
        """Eventi grezzi di una partita, ordinati per timestamp."""
        await ServizioPartita.trova_per_id(db, partita_id)

        stmt = (
            select(EventoGrezzo)
            .where(EventoGrezzo.partita_id == partita_id)
            .order_by(EventoGrezzo.ts_evento)
        )
        if solo_non_validati:
            stmt = stmt.where(EventoGrezzo.validato.is_(False))

        risultato = await db.execute(stmt)
        return risultato.scalars().all()

    @staticmethod
    async def elimina(
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
    ) -> None:
        """Elimina un singolo evento grezzo."""
        stmt = (
            select(EventoGrezzo)
            .where(EventoGrezzo.id == evento_id)
            .where(EventoGrezzo.partita_id == partita_id)
        )
        risultato = await db.execute(stmt)
        evento = risultato.scalar_one_or_none()
        if evento is None:
            raise EventoInesistenteError(
                f"Evento grezzo '{evento_id}' non trovato per partita '{partita_id}'"
            )
        await db.delete(evento)
        await db.commit()

    @staticmethod
    async def elimina_batch(
        db: AsyncSession,
        partita_id: str,
        evento_ids: list[str],
    ) -> int:
        """
        Elimina N eventi grezzi atomicamente. Restituisce il numero
        effettivamente cancellati (alcuni IDs potrebbero non esistere
        o appartenere ad altre partite — sono ignorati silenziosamente).

        Atomico: o tutti gli ID validi vengono cancellati o nessuno
        (single transaction).
        """
        if not evento_ids:
            return 0

        stmt = select(EventoGrezzo).where(
            EventoGrezzo.partita_id == partita_id,
            EventoGrezzo.id.in_(evento_ids),
        )
        risultato = await db.execute(stmt)
        eventi = list(risultato.scalars())
        for ev in eventi:
            await db.delete(ev)
        await db.commit()
        return len(eventi)

    @staticmethod
    async def aggiorna(
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
        dati: EventoGrezzoAggiornamento,
    ) -> EventoGrezzo:
        """
        Modifica parziale di un evento grezzo (solo i campi presenti
        nel body vengono aggiornati).
        """
        stmt = (
            select(EventoGrezzo)
            .where(EventoGrezzo.id == evento_id)
            .where(EventoGrezzo.partita_id == partita_id)
        )
        risultato = await db.execute(stmt)
        evento = risultato.scalar_one_or_none()
        if evento is None:
            raise EventoInesistenteError(
                f"Evento grezzo '{evento_id}' non trovato per partita '{partita_id}'"
            )

        for campo, valore in dati.model_dump(exclude_unset=True).items():
            if campo == "dati" and valore is not None:
                evento.dati = dict(valore)
            else:
                setattr(evento, campo, valore)

        await db.commit()
        await db.refresh(evento)
        return evento


# === Servizio Eventi Validati ===


class ServizioEventiValidati:
    """Gestione eventi validati (pronti per il motore regole)."""

    @staticmethod
    async def crea(
        db: AsyncSession,
        partita_id: str,
        dati: EventoValidatoCreazione,
    ) -> EventoValidato:
        """
        Promuove un evento grezzo a validato, oppure crea un evento da zero.

        Se `evento_grezzo_id` è specificato, marca anche quel grezzo come
        validato (riferimento bidirezionale).
        """
        await ServizioPartita.trova_per_id(db, partita_id)

        evento_validato = EventoValidato(
            partita_id=partita_id,
            ts_evento=dati.ts_evento,
            tipo=dati.tipo,
            dati=dict(dati.dati),
            evento_grezzo_id=dati.evento_grezzo_id,
            validato_da=dati.validato_da,
        )
        db.add(evento_validato)

        if dati.evento_grezzo_id is not None:
            stmt = (
                select(EventoGrezzo)
                .where(EventoGrezzo.id == dati.evento_grezzo_id)
                .where(EventoGrezzo.partita_id == partita_id)
            )
            risultato = await db.execute(stmt)
            grezzo = risultato.scalar_one_or_none()
            if grezzo is None:
                raise EventoInesistenteError(
                    f"Evento grezzo di riferimento '{dati.evento_grezzo_id}' non trovato"
                )
            grezzo.validato = True

        await db.commit()
        await db.refresh(evento_validato)
        return evento_validato

    @staticmethod
    async def crea_batch(
        db: AsyncSession,
        partita_id: str,
        eventi: list[EventoValidatoCreazione],
    ) -> list[EventoValidato]:
        """
        Inserimento atomico di più eventi validati.

        Caso d'uso principale: setup automatico di una partita (42
        territori + obiettivi + partita_inizio in un'unica transazione).
        Anche utile per import futuri da tablet osservatore.

        Eventuali `evento_grezzo_id` di riferimento marcano i grezzi
        corrispondenti come validati nello stesso commit.
        """
        await ServizioPartita.trova_per_id(db, partita_id)

        # Pre-fetch dei grezzi referenziati, per validare in massa e
        # marcarli tutti nello stesso flush.
        ids_grezzi_richiesti = [
            e.evento_grezzo_id for e in eventi if e.evento_grezzo_id is not None
        ]
        grezzi_per_id: dict[str, EventoGrezzo] = {}
        if ids_grezzi_richiesti:
            stmt = (
                select(EventoGrezzo)
                .where(EventoGrezzo.partita_id == partita_id)
                .where(EventoGrezzo.id.in_(ids_grezzi_richiesti))
            )
            risultato = await db.execute(stmt)
            for g in risultato.scalars().all():
                grezzi_per_id[g.id] = g

            # Verifica che tutti gli id richiesti esistano
            mancanti = set(ids_grezzi_richiesti) - set(grezzi_per_id.keys())
            if mancanti:
                raise EventoInesistenteError(
                    f"Eventi grezzi referenziati non trovati: {sorted(mancanti)}"
                )

        oggetti = [
            EventoValidato(
                partita_id=partita_id,
                ts_evento=e.ts_evento,
                tipo=e.tipo,
                dati=dict(e.dati),
                evento_grezzo_id=e.evento_grezzo_id,
                validato_da=e.validato_da,
            )
            for e in eventi
        ]
        db.add_all(oggetti)

        # Marca i grezzi referenziati come validati
        for g in grezzi_per_id.values():
            g.validato = True

        await db.commit()
        for o in oggetti:
            await db.refresh(o)
        return oggetti

    @staticmethod
    async def lista(
        db: AsyncSession,
        partita_id: str,
    ) -> Sequence[EventoValidato]:
        """Eventi validati di una partita, ordinati per timestamp."""
        await ServizioPartita.trova_per_id(db, partita_id)

        stmt = (
            select(EventoValidato)
            .where(EventoValidato.partita_id == partita_id)
            .order_by(EventoValidato.ts_evento)
        )
        risultato = await db.execute(stmt)
        return risultato.scalars().all()

    @staticmethod
    async def aggiorna(
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
        dati: EventoValidatoAggiornamento,
    ) -> EventoValidato:
        """
        Aggiorna un evento validato esistente.

        Permette di correggere ts_evento, tipo, payload `dati` o validato_da
        durante la review. Solo i campi presenti nel body vengono modificati.

        Importante: dopo un aggiornamento, lo snapshot ricostruito non è più
        valido — il client dovrebbe richiamare POST /ricostruisci.
        """
        stmt = (
            select(EventoValidato)
            .where(EventoValidato.id == evento_id)
            .where(EventoValidato.partita_id == partita_id)
        )
        risultato = await db.execute(stmt)
        evento = risultato.scalar_one_or_none()
        if evento is None:
            raise EventoInesistenteError(
                f"Evento validato '{evento_id}' non trovato per partita '{partita_id}'"
            )

        for campo, valore in dati.model_dump(exclude_unset=True).items():
            # `dati` è un dict JSON: lo passiamo per intero (no merge parziale)
            setattr(evento, campo, valore)

        await db.commit()
        await db.refresh(evento)
        return evento

    @staticmethod
    async def elimina(
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
    ) -> None:
        """
        Elimina un evento validato.

        Se l'evento era stato promosso da un grezzo, il grezzo NON viene
        marcato come non-validato in modo automatico — è comportamento
        intenzionale, perché il grezzo originale resta lì e l'utente potrà
        decidere se promuoverlo di nuovo o eliminarlo a sua volta.
        """
        stmt = (
            select(EventoValidato)
            .where(EventoValidato.id == evento_id)
            .where(EventoValidato.partita_id == partita_id)
        )
        risultato = await db.execute(stmt)
        evento = risultato.scalar_one_or_none()
        if evento is None:
            raise EventoInesistenteError(
                f"Evento validato '{evento_id}' non trovato per partita '{partita_id}'"
            )
        await db.delete(evento)
        await db.commit()
