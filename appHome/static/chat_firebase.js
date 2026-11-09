import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-app.js";
import {
    getAuth,
    initializeAuth,
    inMemoryPersistence,
    signInWithCustomToken,
} from "https://www.gstatic.com/firebasejs/13.2.0/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-firestore.js";

const APP_NAME = "vallet-web-chat";

let conexao = null;

function lerConfiguracao() {
    const elemento = document.getElementById("firebase-chat-config");
    if (!elemento) {
        throw new Error("Configuração do Firebase não encontrada na página.");
    }

    try {
        const config = JSON.parse(elemento.textContent || "{}");
        if (!config.apiKey || !config.projectId || !config.tokenUrl) {
            throw new Error("Configuração do Firebase incompleta.");
        }
        return config;
    } catch (erro) {
        throw new Error(`Configuração do Firebase inválida: ${erro.message}`);
    }
}

function obterAuth(app) {
    try {
        return initializeAuth(app, { persistence: inMemoryPersistence });
    } catch (_) {
        return getAuth(app);
    }
}

async function criarConexao() {
    const config = lerConfiguracao();
    const {
        tokenUrl,
        chatUrl,
        collection: colecao,
        estacionamentoId,
        ...firebaseConfig
    } = config;

    const app =
        getApps().find((instancia) => instancia.name === APP_NAME) ||
        initializeApp(firebaseConfig, APP_NAME);

    const auth = obterAuth(app);

    const resposta = await fetch(tokenUrl, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
            Accept: "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    });

    if (resposta.redirected) {
        window.location.assign(resposta.url || "/login/");
        throw new Error("Sua sessão expirou. Faça login novamente.");
    }

    let dados;
    try {
        dados = await resposta.json();
    } catch (_) {
        throw new Error("O servidor retornou uma resposta inválida para o chat.");
    }

    if (!resposta.ok || !dados.token) {
        if (resposta.status === 401 && dados.login_url) {
            window.location.assign(dados.login_url);
        }
        throw new Error(dados.detail || "Não foi possível iniciar o chat.");
    }

    const credencial = await signInWithCustomToken(auth, dados.token);
    const token = await credencial.user.getIdTokenResult();
    const claims = token.claims || {};

    return {
        app,
        auth,
        db: getFirestore(app),
        colecao: colecao || "chat",
        perfil: {
            uid: credencial.user.uid,
            tipo: claims.tipo_user || dados.tipo || "gestor",
            nome: claims.nome || dados.nome || "Usuário",
            estacionamentoId:
                claims.estacionamentoId || dados.estacionamentoId || estacionamentoId || "",
            estacionamentoNome: dados.estacionamentoNome || "",
        },
    };
}

/**
 * Autentica no Firebase com um token de curta duração emitido pela API.
 */
export function conectarFirebaseChat() {
    if (!conexao) {
        conexao = criarConexao().catch((erro) => {
            conexao = null;
            throw erro;
        });
    }
    return conexao;
}
