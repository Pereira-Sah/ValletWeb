import {
    collection,
    doc,
    getDoc,
    limitToLast,
    onSnapshot,
    orderBy,
    query,
    runTransaction,
    serverTimestamp,
    setDoc,
    updateDoc,
} from "https://www.gstatic.com/firebasejs/13.2.0/firebase-firestore.js";
import { conectarFirebaseChat } from "./chat_firebase.js";

const raiz = document.getElementById("chatPage");
const lista = document.getElementById("chatMessages");
const formulario = document.getElementById("chatForm");
const campo = document.getElementById("chatInput");
const botao = document.getElementById("chatSend");
const feedback = document.getElementById("chatFeedback");
const status = document.getElementById("chatConnection");

let conexao = null;
let perfil = null;
let estacionamentoId = "";
let estacionamentoNome = "";
let conversa = null;
let pararConversa = null;
let pararMensagens = null;
let enviando = false;
let marcandoLeitura = false;
let iniciado = false;

function definirStatus(estado, texto) {
    if (!status) return;
    status.dataset.state = estado;
    const rotulo = status.querySelector("span");
    if (rotulo) rotulo.textContent = texto;
}

function mostrarErro(mensagem) {
    if (!feedback) return;
    feedback.textContent = mensagem;
    feedback.hidden = !mensagem;
}

function limparErro() {
    mostrarErro("");
}

function iniciais(nome) {
    const partes = String(nome || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);

    if (!partes.length) return "?";
    if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
    return `${partes[0][0]}${partes[partes.length - 1][0]}`.toUpperCase();
}

function formatarHorario(mensagem) {
    let data = null;

    if (mensagem?.criadoEm?.toDate) {
        data = mensagem.criadoEm.toDate();
    } else if (typeof mensagem?.criadoEmCliente === "number") {
        data = new Date(mensagem.criadoEmCliente);
    }

    if (!data || Number.isNaN(data.getTime())) return "Enviando…";

    const agora = new Date();
    const mesmoDia =
        data.getDate() === agora.getDate() &&
        data.getMonth() === agora.getMonth() &&
        data.getFullYear() === agora.getFullYear();

    if (mesmoDia) {
        return data.toLocaleTimeString("pt-BR", {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    return data.toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function criarMensagem(mensagem) {
    const propria = mensagem.autorUid === perfil.uid;
    const artigo = document.createElement("article");
    artigo.className = propria
        ? "chat-message chat-message--gestor"
        : "chat-message chat-message--admin";
    if (mensagem.criadoEm === null || mensagem.criadoEm === undefined) {
        artigo.classList.add("chat-message--pending");
    }

    const avatar = document.createElement("div");
    avatar.className = "chat-message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = iniciais(mensagem.autorNome || (propria ? "Eu" : "AD"));

    const conteudo = document.createElement("div");
    conteudo.className = "chat-message-content";

    const meta = document.createElement("div");
    meta.className = "chat-message-meta";

    const autor = document.createElement("strong");
    autor.textContent = propria ? "Você" : (mensagem.autorNome || "Administrador");

    const horario = document.createElement("span");
    horario.textContent = formatarHorario(mensagem);

    meta.append(autor, horario);

    const bolha = document.createElement("div");
    bolha.className = "chat-message-bubble";
    bolha.textContent = mensagem.texto || "";

    conteudo.append(meta, bolha);
    artigo.append(avatar, conteudo);
    return artigo;
}

function renderizarMensagens(mensagens) {
    if (!lista) return;

    const pertoDoFim =
        lista.scrollHeight - lista.scrollTop - lista.clientHeight < 140;
    const primeiraCarga = lista.getAttribute("aria-busy") === "true";

    lista.replaceChildren();
    lista.setAttribute("aria-busy", "false");

    if (!mensagens.length) {
        const vazio = document.createElement("p");
        vazio.className = "chat-empty";
        vazio.textContent =
            "Nenhuma mensagem ainda. Envie a primeira para falar com o administrador supremo.";
        lista.append(vazio);
        return;
    }

    const fragmento = document.createDocumentFragment();
    mensagens.forEach((mensagem) => fragmento.append(criarMensagem(mensagem)));
    lista.append(fragmento);

    if (primeiraCarga || pertoDoFim) {
        lista.scrollTop = lista.scrollHeight;
    }
}

async function marcarComoLida() {
    if (
        !conversa ||
        !conexao ||
        marcandoLeitura ||
        !Number(conversa.naoLidasGestor) ||
        document.visibilityState !== "visible"
    ) {
        return;
    }

    marcandoLeitura = true;
    try {
        await updateDoc(doc(conexao.db, conexao.colecao, estacionamentoId), {
            naoLidasGestor: 0,
        });
    } catch (erro) {
        console.warn("[chat] Não foi possível marcar como lida:", erro);
    } finally {
        window.setTimeout(() => {
            marcandoLeitura = false;
        }, 800);
    }
}

function observarConversa() {
    const referencia = doc(conexao.db, conexao.colecao, estacionamentoId);
    pararConversa?.();

    pararConversa = onSnapshot(
        referencia,
        (snapshot) => {
            conversa = snapshot.data() || null;
            marcarComoLida();
        },
        (erro) => {
            console.warn("[chat] Conversa indisponível:", erro);
            mostrarErro(
                "Não foi possível acompanhar a conversa em tempo real. Verifique as regras do Firestore.",
            );
        },
    );
}

function observarMensagens() {
    const consulta = query(
        collection(conexao.db, conexao.colecao, estacionamentoId, "mensagens"),
        orderBy("criadoEmCliente", "asc"),
        limitToLast(500),
    );

    pararMensagens?.();
    pararMensagens = onSnapshot(
        consulta,
        (snapshot) => {
            const mensagens = snapshot.docs.map((documento) => ({
                id: documento.id,
                ...documento.data(),
            }));
            renderizarMensagens(mensagens);
            marcarComoLida();
        },
        (erro) => {
            console.warn("[chat] Mensagens indisponíveis:", erro);
            if (lista) {
                lista.setAttribute("aria-busy", "false");
                lista.replaceChildren();
                const aviso = document.createElement("p");
                aviso.className = "chat-empty";
                aviso.textContent =
                    "Não foi possível carregar as mensagens. Confira sua conexão e as regras do Firestore.";
                lista.append(aviso);
            }
            definirStatus("error", "Sem conexão");
            mostrarErro(
                "Falha ao ouvir as mensagens em tempo real. Verifique as regras do Firestore para a coleção chat.",
            );
        },
    );
}

async function garantirConversa() {
    const referencia = doc(conexao.db, conexao.colecao, estacionamentoId);
    const atual = await getDoc(referencia);

    if (atual.exists()) return;

    await setDoc(
        referencia,
        {
            estacionamentoId,
            estacionamentoNome,
            gestorUid: perfil.uid,
            gestorNome: perfil.nome || "Gestor",
            criadoEm: serverTimestamp(),
            atualizadoEm: serverTimestamp(),
            naoLidasGestor: 0,
            naoLidasSuperadmin: 0,
        },
        { merge: true },
    );
}

async function enviarMensagem(texto) {
    if (enviando) return;

    enviando = true;
    botao?.setAttribute("disabled", "disabled");
    limparErro();
    ajustarAltura();

    try {
        const conversaRef = doc(conexao.db, conexao.colecao, estacionamentoId);
        const mensagemRef = doc(
            collection(conexao.db, conexao.colecao, estacionamentoId, "mensagens"),
        );

        await runTransaction(conexao.db, async (transacao) => {
            const atual = await transacao.get(conversaRef);
            const dadosAtuais = atual.exists() ? atual.data() : {};
            const agora = serverTimestamp();

            transacao.set(
                conversaRef,
                {
                    estacionamentoId,
                    estacionamentoNome,
                    gestorUid: perfil.uid,
                    gestorNome: perfil.nome || "Gestor",
                    ultimaMensagem: texto.slice(0, 180),
                    ultimaMensagemEm: agora,
                    ultimaMensagemAutor: perfil.uid,
                    ultimaMensagemAutorNome: perfil.nome || "Gestor",
                    atualizadoEm: agora,
                    naoLidasSuperadmin:
                        (Number(dadosAtuais.naoLidasSuperadmin) || 0) + 1,
                },
                { merge: true },
            );

            transacao.set(mensagemRef, {
                texto,
                autorUid: perfil.uid,
                autorNome: perfil.nome || "Gestor",
                autorTipo: "gestor",
                criadoEm: serverTimestamp(),
                criadoEmCliente: Date.now(),
            });
        });

        campo.value = "";
        ajustarAltura();
    } catch (erro) {
        console.error("[chat] Falha ao enviar:", erro);
        mostrarErro(
            `Não foi possível enviar a mensagem. ${erro.message || "Tente novamente."}`,
        );
    } finally {
        enviando = false;
        botao?.removeAttribute("disabled");
        campo.focus();
    }
}

function ajustarAltura() {
    if (!campo) return;
    campo.style.height = "auto";
    campo.style.height = `${Math.min(campo.scrollHeight, 150)}px`;
}

async function iniciar() {
    if (iniciado || !raiz) return;
    iniciado = true;

    definirStatus("connecting", "Conectando…");
    limparErro();
    campo?.setAttribute("disabled", "disabled");
    botao?.setAttribute("disabled", "disabled");

    try {
        conexao = await conectarFirebaseChat();
        perfil = conexao.perfil;
        estacionamentoId =
            perfil.estacionamentoId || raiz.dataset.estacionamentoId || "";
        estacionamentoNome =
            perfil.estacionamentoNome ||
            raiz.dataset.estacionamentoNome ||
            "Seu estacionamento";

        if (!estacionamentoId) {
            throw new Error(
                "Nenhum estacionamento está vinculado a este gestor. Fale com o administrador supremo.",
            );
        }

        await garantirConversa();
        observarConversa();
        observarMensagens();

        definirStatus("online", "Conectado em tempo real");
        campo?.removeAttribute("disabled");
        botao?.removeAttribute("disabled");
        campo?.focus();
    } catch (erro) {
        console.error("[chat] Falha ao iniciar:", erro);
        definirStatus("error", "Chat indisponível");
        mostrarErro(erro.message || "Não foi possível iniciar o chat.");
        if (lista) {
            lista.setAttribute("aria-busy", "false");
            lista.replaceChildren();
            const aviso = document.createElement("p");
            aviso.className = "chat-empty";
            aviso.textContent =
                erro.message || "Não foi possível carregar a conversa.";
            lista.append(aviso);
        }
    }
}

formulario?.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const texto = String(campo?.value || "").trim();
    if (!texto) return;
    enviarMensagem(texto);
});

campo?.addEventListener("input", ajustarAltura);

campo?.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey) {
        evento.preventDefault();
        formulario?.requestSubmit();
    }
});

document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
        marcarComoLida();
        if (lista && lista.scrollHeight - lista.scrollTop - lista.clientHeight < 140) {
            lista.scrollTop = lista.scrollHeight;
        }
    }
});

window.addEventListener("beforeunload", () => {
    pararConversa?.();
    pararMensagens?.();
});

iniciar();
