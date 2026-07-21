function mostrarSenha(){

    const senha=document.getElementById("senha");

    const icone=document.getElementById("iconeSenha");

    if(senha.type==="password"){

        senha.type="text";

        icone.setAttribute("data-lucide","eye-off");

    }else{

        senha.type="password";

        icone.setAttribute("data-lucide","eye");

    }

    lucide.createIcons();

}