import { doc, onSnapshot } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-firestore.js";
import { conectarFirebaseChat } from "./chat_firebase.js";

const contador = document.getElementById("navbar-chat-count");
const link = document.getElementById("navbar-chat-link");

function atualizarContador(total) {
    if (!contador) return;

    const valor = Number.isFinite(total) ? Math.max(0, total) : 0;
    contador.textContent = valor > 99 ? "99+" : String(valor);
    contador.hidden = valor === 0;
    link?.classList.toggle("has-chat-unread", valor > 0);
}

async function iniciarContador() {
    if (!contador) return;

    try {
        const conexao = await conectarFirebaseChat();
        const estacionamentoId =
            conexao.perfil.estacionamentoId ||
            document.getElementById("chatPage")?.dataset.estacionamentoId ||
            "";

        if (!estacionamentoId) {
            atualizarContador(0);
            return;
        }

        onSnapshot(
            doc(conexao.db, conexao.colecao, estacionamentoId),
            (snapshot) => {
                const dados = snapshot.data() || {};
                atualizarContador(Number(dados.naoLidasGestor) || 0);
            },
            (erro) => {
                console.warn("[chat] Não foi possível acompanhar as mensagens:", erro);
                atualizarContador(0);
            },
        );
    } catch (erro) {
        console.warn("[chat] Contador indisponível:", erro.message);
    }
}

iniciarContador();
