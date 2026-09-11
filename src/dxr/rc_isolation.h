#pragma once

struct RcHandle {
    HANDLE value{};
    ~RcHandle() { if(value&&value!=INVALID_HANDLE_VALUE) CloseHandle(value); }
    void Close() { if(value&&value!=INVALID_HANDLE_VALUE) CloseHandle(value); value=nullptr; }
    RcHandle()=default; RcHandle(const RcHandle&)=delete; RcHandle& operator=(const RcHandle&)=delete;
};
std::wstring RcArgument(const std::wstring& value) {
    std::wstring result=L"\""; size_t slashes=0;
    for(wchar_t c:value) {
        if(c==L'\\') { ++slashes; continue; }
        result.append(c==L'"'?slashes*2+1:slashes,L'\\'); result+=c; slashes=0;
    }
    result.append(slashes*2,L'\\'); result+=L'"'; return result;
}
struct RcAttributes {
    std::vector<unsigned char> storage; LPPROC_THREAD_ATTRIBUTE_LIST list{};
    RcAttributes(HANDLE* handles,size_t count) {
        SIZE_T size=0; InitializeProcThreadAttributeList(nullptr,1,0,&size); Require(size>0,"RC worker attribute size failed");
        storage.resize(size); list=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
        Require(InitializeProcThreadAttributeList(list,1,0,&size)!=FALSE,"RC worker attribute initialization failed");
        if(!UpdateProcThreadAttribute(list,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,handles,count*sizeof(HANDLE),nullptr,nullptr)) {
            DeleteProcThreadAttributeList(list); list=nullptr; throw std::runtime_error("RC worker handle list failed");
        }
    }
    ~RcAttributes() { if(list) DeleteProcThreadAttributeList(list); }
};
struct RcProcessResult {
    static constexpr size_t OutputLimit=65536;
    std::string output,error; DWORD exitCode{},processId{}; bool timedOut{},overflow{},reaped{};
    std::string Json() const {
        std::ostringstream out;
        out << "{\"protocol\":\"rc-isolation-1\",\"job_assigned_before_resume\":true,\"child_reaped\":" << (reaped?"true":"false")
            << ",\"exit_code\":" << exitCode << ",\"child_pid\":" << processId
            << ",\"timed_out\":" << (timedOut?"true":"false") << ",\"output_limit_exceeded\":" << (overflow?"true":"false")
            << ",\"output_limit_bytes\":" << OutputLimit << ",\"stdout\":" << QuoteBytes(output) << ",\"stderr\":" << QuoteBytes(error) << '}';
        return out.str();
    }
};
struct RcIsolatedSession {
    RcHandle outRead,errRead,job,process;
    DWORD processId{}; bool finished{},timedOut{},overflow{}; std::string output,error;
    RcIsolatedSession(const std::vector<std::wstring>& arguments,const std::vector<HANDLE>& extraInherited,const wchar_t* externalExecutable) {
        Require(externalExecutable&&*externalExecutable,"RC live worker path invalid"); std::wstring application=externalExecutable,command=RcArgument(application); for(const auto& argument:arguments) command+=L" "+RcArgument(argument); Require(command.size()<32767,"RC live worker command line exceeds limit");
        SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE}; RcHandle outWrite,errWrite,input,thread;
        Require(CreatePipe(&outRead.value,&outWrite.value,&security,0)&&CreatePipe(&errRead.value,&errWrite.value,&security,0),"RC live worker pipe failed");
        Require(SetHandleInformation(outRead.value,HANDLE_FLAG_INHERIT,0)&&SetHandleInformation(errRead.value,HANDLE_FLAG_INHERIT,0),"RC live pipe inheritance failed");
        input.value=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,OPEN_EXISTING,0,nullptr); Require(input.value!=INVALID_HANDLE_VALUE,"RC live stdin failed");
        job.value=CreateJobObjectW(nullptr,nullptr); Require(job.value!=nullptr,"RC live job creation failed"); JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{}; limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_ACTIVE_PROCESS; limits.BasicLimitInformation.ActiveProcessLimit=1; Require(SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)),"RC live job limits failed");
        std::vector<HANDLE> inherited={outWrite.value,errWrite.value,input.value}; inherited.insert(inherited.end(),extraInherited.begin(),extraInherited.end()); RcAttributes attributes(inherited.data(),inherited.size());
        STARTUPINFOEXW startup{}; startup.StartupInfo.cb=sizeof(startup); startup.lpAttributeList=attributes.list; startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES; startup.StartupInfo.hStdInput=input.value; startup.StartupInfo.hStdOutput=outWrite.value; startup.StartupInfo.hStdError=errWrite.value; PROCESS_INFORMATION info{};
        Require(CreateProcessW(application.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_SUSPENDED|CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT,nullptr,nullptr,&startup.StartupInfo,&info),"RC live worker process creation failed"); process.value=info.hProcess; thread.value=info.hThread; processId=info.dwProcessId;
        if(!AssignProcessToJobObject(job.value,process.value)) { TerminateProcess(process.value,1); WaitForSingleObject(process.value,5000); throw std::runtime_error("RC live worker job assignment failed"); }
        if(ResumeThread(thread.value)==DWORD(-1)) { Abort(false); throw std::runtime_error("RC live worker resume failed"); } thread.Close(); outWrite.Close(); errWrite.Close(); input.Close();
    }
    RcIsolatedSession(const RcIsolatedSession&)=delete; RcIsolatedSession& operator=(const RcIsolatedSession&)=delete;
    ~RcIsolatedSession() { if(process.value&&!finished&&WaitForSingleObject(process.value,0)!=WAIT_OBJECT_0) { TerminateJobObject(job.value,1); WaitForSingleObject(process.value,5000); } }
    void Drain(HANDLE pipe,std::string& destination) {
        DWORD available=0; if(!PeekNamedPipe(pipe,nullptr,0,nullptr,&available,nullptr)) { Require(GetLastError()==ERROR_BROKEN_PIPE,"RC live pipe inspection failed"); return; }
        while(available) { char bytes[4096]; DWORD count=0; const DWORD requested=std::min(available,DWORD(sizeof(bytes))); Require(ReadFile(pipe,bytes,requested,&count,nullptr)&&count,"RC live pipe read failed"); const size_t room=RcProcessResult::OutputLimit-destination.size(); destination.append(bytes,std::min(room,size_t(count))); if(count>room) { overflow=true; return; } available-=count; }
    }
    void Abort(bool timeout) { timedOut=timeout; Require(TerminateJobObject(job.value,1),"RC live worker termination failed"); Require(WaitForSingleObject(process.value,5000)==WAIT_OBJECT_0,"RC live worker did not terminate"); finished=true; }
    bool PollFence(ID3D12Fence* fence,uint64_t value) {
        Require(fence!=nullptr,"RC live fence missing");
        Drain(outRead.value,output); Drain(errRead.value,error);
        if(overflow) { Abort(false); throw std::runtime_error("RC live worker output limit exceeded"); }
        const uint64_t completed=fence->GetCompletedValue();
        Require(completed!=UINT64_MAX,"RC live fence device removed");
        if(completed>=value) return true;
        const DWORD state=WaitForSingleObject(process.value,0);
        Require(state!=WAIT_FAILED,"RC live worker poll failed");
        if(state==WAIT_OBJECT_0) {
            finished=true;
            // Completion may race with the process-exit observation.
            const uint64_t finalValue=fence->GetCompletedValue();
            Require(finalValue!=UINT64_MAX,"RC live fence device removed");
            if(finalValue>=value) return true;
            throw std::runtime_error("RC live worker exited before fence completion");
        }
        return false;
    }
    void WaitFence(ID3D12Fence* fence,uint64_t value,DWORD timeoutMs) {
        Require(timeoutMs&&timeoutMs<=60000,"RC live fence deadline invalid");
        const auto start=GetTickCount64();
        if(PollFence(fence,value)) return;
        RcHandle event; event.value=CreateEventW(nullptr,FALSE,FALSE,nullptr);
        Require(event.value!=nullptr,"RC live fence event failed");
        Require(SUCCEEDED(fence->SetEventOnCompletion(value,event.value)),"RC live fence completion failed");
        HANDLE waits[]={event.value,process.value};
        for(;;) {
            if(PollFence(fence,value)) return;
            const auto elapsed=GetTickCount64()-start;
            if(elapsed>=timeoutMs) { Abort(true); throw std::runtime_error("RC live worker fence timeout"); }
            const DWORD state=WaitForMultipleObjects(2,waits,FALSE,DWORD(std::min<ULONGLONG>(10,timeoutMs-elapsed)));
            Require(state!=WAIT_FAILED,"RC live worker fence wait failed");
        }
    }
    RcProcessResult Finish(DWORD timeoutMs) {
        Require(timeoutMs&&timeoutMs<=60000,"RC live finish deadline invalid"); const auto start=GetTickCount64(); for(;;) { Drain(outRead.value,output); Drain(errRead.value,error); const DWORD state=WaitForSingleObject(process.value,0); Require(state!=WAIT_FAILED,"RC live worker wait failed"); if(state==WAIT_OBJECT_0) { finished=true; break; } if(overflow||GetTickCount64()-start>=timeoutMs) { Abort(!overflow); break; } WaitForSingleObject(process.value,10); }
        Drain(outRead.value,output); Drain(errRead.value,error); RcProcessResult result; result.output=output; result.error=error; result.processId=processId; result.timedOut=timedOut; result.overflow=overflow; result.reaped=finished; Require(GetExitCodeProcess(process.value,&result.exitCode),"RC live worker exit status unavailable"); return result;
    }
};
RcProcessResult RcRunIsolated(const std::vector<std::wstring>& arguments,DWORD timeoutMs,bool parentExitFixture=false,const std::vector<unsigned char>* stdinBytes=nullptr,const std::vector<HANDLE>* extraInherited=nullptr,const wchar_t* externalExecutable=nullptr) {
    Require(timeoutMs>0&&timeoutMs<=60000,"RC worker deadline out of range");
    wchar_t module[32768]{}; std::wstring application;
    if(externalExecutable) { application=externalExecutable; Require(!application.empty()&&application.size()<32768,"RC external worker path invalid"); }
    else { const DWORD length=GetModuleFileNameW(nullptr,module,32768); Require(length&&length<32768,"RC worker executable path unavailable"); application=module; }
    std::wstring command=RcArgument(application); for(const auto& argument:arguments) command+=L" "+RcArgument(argument);
    Require(command.size()<32767,"RC worker command line exceeds limit");
    SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE};
    RcHandle outRead,outWrite,errRead,errWrite,inputRead,inputWrite,job,process,thread;
    Require(CreatePipe(&outRead.value,&outWrite.value,&security,0)!=FALSE,"RC worker stdout pipe failed");
    Require(CreatePipe(&errRead.value,&errWrite.value,&security,0)!=FALSE,"RC worker stderr pipe failed");
    Require(SetHandleInformation(outRead.value,HANDLE_FLAG_INHERIT,0)&&SetHandleInformation(errRead.value,HANDLE_FLAG_INHERIT,0),"RC pipe inheritance failed");
    if(stdinBytes) {
        Require(!stdinBytes->empty()&&stdinBytes->size()<=2*1024*1024,"RC worker stdin payload outside bound");
        Require(CreatePipe(&inputRead.value,&inputWrite.value,&security,0)!=FALSE,"RC worker stdin pipe failed");
        Require(SetHandleInformation(inputWrite.value,HANDLE_FLAG_INHERIT,0)!=FALSE,"RC worker stdin inheritance failed");
    } else inputRead.value=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,OPEN_EXISTING,0,nullptr);
    Require(inputRead.value!=INVALID_HANDLE_VALUE,"RC worker stdin failed");
    job.value=CreateJobObjectW(nullptr,nullptr); Require(job.value!=nullptr,"RC worker job creation failed");
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{}; limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
    limits.BasicLimitInformation.ActiveProcessLimit=1;
    Require(SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits))!=FALSE,"RC worker job limits failed");
    std::vector<HANDLE> inherited={outWrite.value,errWrite.value,inputRead.value};
    if(extraInherited) inherited.insert(inherited.end(),extraInherited->begin(),extraInherited->end());
    RcAttributes attributes(inherited.data(),inherited.size());
    STARTUPINFOEXW startup{}; startup.StartupInfo.cb=sizeof(startup); startup.lpAttributeList=attributes.list;
    startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES; startup.StartupInfo.hStdInput=inputRead.value;
    startup.StartupInfo.hStdOutput=outWrite.value; startup.StartupInfo.hStdError=errWrite.value;
    PROCESS_INFORMATION info{};
    Require(CreateProcessW(application.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_SUSPENDED|CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT,
                           nullptr,nullptr,&startup.StartupInfo,&info)!=FALSE,"RC worker process creation failed");
    process.value=info.hProcess; thread.value=info.hThread;
    if(!AssignProcessToJobObject(job.value,process.value)) {
        TerminateProcess(process.value,1); WaitForSingleObject(process.value,5000);
        throw std::runtime_error("RC worker job assignment failed; suspended child terminated");
    }
    Require(ResumeThread(thread.value)!=DWORD(-1),"RC worker resume failed");
    thread.Close(); outWrite.Close(); errWrite.Close(); inputRead.Close(); RcProcessResult result; result.processId=info.dwProcessId;
    if(stdinBytes) {
        size_t offset=0; while(offset<stdinBytes->size()) { DWORD written=0; const DWORD count=DWORD(std::min<size_t>(65536,stdinBytes->size()-offset));
            Require(WriteFile(inputWrite.value,stdinBytes->data()+offset,count,&written,nullptr)&&written==count,"RC worker stdin write failed"); offset+=written; }
        inputWrite.Close();
    }
    if(parentExitFixture) { std::cout << "{\"child_pid\":" << result.processId << '}' << std::flush; ExitProcess(55); }
    const auto start=GetTickCount64();
    auto drain=[&](HANDLE pipe,std::string& destination) {
        DWORD available=0; if(!PeekNamedPipe(pipe,nullptr,0,nullptr,&available,nullptr)) { Require(GetLastError()==ERROR_BROKEN_PIPE,"RC pipe inspection failed"); return; }
        while(available) {
            char bytes[4096]; DWORD count=0; const DWORD requested=std::min(available,DWORD(sizeof(bytes)));
            Require(ReadFile(pipe,bytes,requested,&count,nullptr)&&count,"RC pipe read failed");
            const size_t room=RcProcessResult::OutputLimit-destination.size(); destination.append(bytes,std::min(room,size_t(count)));
            if(count>room) { result.overflow=true; return; } available-=count;
        }
    };
    for(;;) {
        drain(outRead.value,result.output); drain(errRead.value,result.error);
        const DWORD state=WaitForSingleObject(process.value,0); Require(state!=WAIT_FAILED,"RC worker wait failed");
        if(state==WAIT_OBJECT_0) { result.reaped=true; break; }
        result.timedOut=GetTickCount64()-start>=timeoutMs;
        if(result.timedOut||result.overflow) {
            Require(TerminateJobObject(job.value,1)!=FALSE,"RC worker termination failed");
            Require(WaitForSingleObject(process.value,5000)==WAIT_OBJECT_0,"RC worker did not terminate"); result.reaped=true; break;
        }
        WaitForSingleObject(process.value,10);
    }
    drain(outRead.value,result.output); drain(errRead.value,result.error);
    Require(GetExitCodeProcess(process.value,&result.exitCode)!=FALSE,"RC worker exit status unavailable"); return result;
}
int RcIsolationChild(const std::wstring& scenario) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
    if(scenario==L"success") { std::cout << "{\"fixture\":true}"; return 0; }
    if(scenario==L"failure") return 9;
    if(scenario==L"malformed") { std::cout << "not-json"; return 0; }
    if(scenario==L"nul") { std::cout.write("{}\0extra",8); return 0; }
    if(scenario==L"timeout") { Sleep(5000); return 0; }
    if(scenario==L"overflow") { for(int i=0;i<100;++i) std::cout << std::string(4096,'x') << std::flush; return 0; }
    if(scenario==L"crash") { RaiseException(0xe0005243,EXCEPTION_NONCONTINUABLE,0,nullptr); return 1; }
    throw std::runtime_error("unknown RC isolation fixture");
}
