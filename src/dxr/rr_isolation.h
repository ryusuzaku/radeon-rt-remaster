#pragma once

struct RrHandle {
    HANDLE value{};
    ~RrHandle() { Close(); }
    void Close() { if(value&&value!=INVALID_HANDLE_VALUE) CloseHandle(value); value=nullptr; }
    RrHandle()=default;
    RrHandle(const RrHandle&)=delete;
    RrHandle& operator=(const RrHandle&)=delete;
};
std::wstring RrArgument(const std::wstring& value) {
    std::wstring result=L"\""; size_t slashes=0;
    for(wchar_t c:value) {
        if(c==L'\\') { ++slashes; continue; }
        result.append(c==L'"'?slashes*2+1:slashes,L'\\'); result+=c; slashes=0;
    }
    result.append(slashes*2,L'\\'); result+=L'"'; return result;
}
struct RrAttributes {
    std::vector<unsigned char> storage;
    LPPROC_THREAD_ATTRIBUTE_LIST list{};
    RrAttributes(HANDLE* handles,size_t count) {
        SIZE_T size=0; InitializeProcThreadAttributeList(nullptr,1,0,&size);
        Require(size>0,"worker attribute size failed"); storage.resize(size);
        auto* candidate=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
        Require(InitializeProcThreadAttributeList(candidate,1,0,&size)!=FALSE,"worker attribute initialization failed"); list=candidate;
        if(!UpdateProcThreadAttribute(list,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,handles,count*sizeof(HANDLE),nullptr,nullptr)) {
            DeleteProcThreadAttributeList(list); list=nullptr; throw std::runtime_error("worker handle list failed");
        }
    }
    ~RrAttributes() { if(list) DeleteProcThreadAttributeList(list); }
};
struct RrProcessResult {
    static constexpr size_t OutputLimit=65536;
    std::string output,error;
    DWORD exitCode{},processId{};
    bool timedOut{},overflow{},reaped{};
    std::string Json() const {
        std::ostringstream out;
        out << "{\"protocol\":\"rr-isolation-1\",\"job_assigned_before_resume\":true,\"child_reaped\":" << (reaped?"true":"false")
            << ",\"exit_code\":" << exitCode << ",\"child_pid\":" << processId
            << ",\"timed_out\":" << (timedOut?"true":"false") << ",\"output_limit_exceeded\":" << (overflow?"true":"false")
            << ",\"output_limit_bytes\":" << OutputLimit << ",\"stdout\":" << QuoteBytes(output) << ",\"stderr\":" << QuoteBytes(error) << '}';
        return out.str();
    }
};

RrProcessResult RrRunIsolated(const std::vector<std::wstring>& arguments,DWORD timeoutMs,bool parentExitFixture=false) {
    Require(timeoutMs>0&&timeoutMs<=60000,"worker deadline out of range");
    wchar_t module[32768]{}; const DWORD length=GetModuleFileNameW(nullptr,module,32768);
    Require(length&&length<32768,"worker executable path unavailable");
    std::wstring command=RrArgument(module);
    for(const auto& argument:arguments) command+=L" "+RrArgument(argument);
    Require(command.size()<32767,"worker command line exceeds limit");
    SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE};
    RrHandle outRead,outWrite,errRead,errWrite,input,job,process,thread;
    Require(CreatePipe(&outRead.value,&outWrite.value,&security,0)!=FALSE,"worker stdout pipe failed");
    Require(CreatePipe(&errRead.value,&errWrite.value,&security,0)!=FALSE,"worker stderr pipe failed");
    Require(SetHandleInformation(outRead.value,HANDLE_FLAG_INHERIT,0)&&SetHandleInformation(errRead.value,HANDLE_FLAG_INHERIT,0),"worker pipe inheritance failed");
    input.value=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,OPEN_EXISTING,0,nullptr);
    Require(input.value!=INVALID_HANDLE_VALUE,"worker stdin failed");
    job.value=CreateJobObjectW(nullptr,nullptr); Require(job.value!=nullptr,"worker job creation failed");
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
    limits.BasicLimitInformation.ActiveProcessLimit=1;
    Require(SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits))!=FALSE,"worker job limits failed");
    HANDLE inherited[]={outWrite.value,errWrite.value,input.value}; RrAttributes attributes(inherited,3);
    STARTUPINFOEXW startup{}; startup.StartupInfo.cb=sizeof(startup); startup.lpAttributeList=attributes.list;
    startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES; startup.StartupInfo.hStdInput=input.value;
    startup.StartupInfo.hStdOutput=outWrite.value; startup.StartupInfo.hStdError=errWrite.value;
    PROCESS_INFORMATION info{};
    Require(CreateProcessW(module,command.data(),nullptr,nullptr,TRUE,CREATE_SUSPENDED|CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT,
                           nullptr,nullptr,&startup.StartupInfo,&info)!=FALSE,"worker process creation failed");
    process.value=info.hProcess; thread.value=info.hThread;
    if(!AssignProcessToJobObject(job.value,process.value)) {
        TerminateProcess(process.value,1); WaitForSingleObject(process.value,5000);
        throw std::runtime_error("worker job assignment failed; suspended child terminated");
    }
    Require(ResumeThread(thread.value)!=DWORD(-1),"worker resume failed");
    thread.Close(); outWrite.Close(); errWrite.Close(); input.Close();
    RrProcessResult result; result.processId=info.dwProcessId;
    if(parentExitFixture) {
        std::cout << "{\"child_pid\":" << result.processId << "}" << std::flush;
        ExitProcess(55); // Fixture: OS handle closure must kill the job's child.
    }
    const auto start=GetTickCount64();
    auto drain=[&](HANDLE pipe,std::string& destination) {
        DWORD available=0;
        if(!PeekNamedPipe(pipe,nullptr,0,nullptr,&available,nullptr)) {
            Require(GetLastError()==ERROR_BROKEN_PIPE,"worker pipe inspection failed"); return;
        }
        // Read only the current snapshot so a flooding child cannot starve the deadline.
        while(available) {
            char bytes[4096]; DWORD count=0;
            const DWORD requested=std::min(available,DWORD(sizeof(bytes)));
            Require(ReadFile(pipe,bytes,requested,&count,nullptr)&&count,"worker pipe read failed");
            const size_t room=RrProcessResult::OutputLimit-destination.size();
            destination.append(bytes,std::min(room,size_t(count)));
            if(count>room) { result.overflow=true; return; }
            available-=count;
        }
    };
    for(;;) {
        drain(outRead.value,result.output); drain(errRead.value,result.error);
        const DWORD state=WaitForSingleObject(process.value,0);
        Require(state!=WAIT_FAILED,"worker wait failed");
        if(state==WAIT_OBJECT_0) { result.reaped=true; break; }
        result.timedOut=GetTickCount64()-start>=timeoutMs;
        if(result.timedOut||result.overflow) {
            Require(TerminateJobObject(job.value,1)!=FALSE,"worker termination failed");
            Require(WaitForSingleObject(process.value,5000)==WAIT_OBJECT_0,"worker did not terminate");
            result.reaped=true; break;
        }
        WaitForSingleObject(process.value,10);
    }
    drain(outRead.value,result.output); drain(errRead.value,result.error);
    Require(GetExitCodeProcess(process.value,&result.exitCode)!=FALSE,"worker exit status unavailable");
    return result;
}

int RrIsolationChild(const std::wstring& scenario) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
    if(scenario==L"success") { std::cout << "{\"fixture\":true}"; return 0; }
    if(scenario==L"failure") return 9;
    if(scenario==L"malformed") { std::cout << "not-json"; return 0; }
    if(scenario==L"nul") { std::cout.write("{}\0extra",8); return 0; }
    if(scenario==L"timeout") { Sleep(5000); return 0; }
    if(scenario==L"overflow") { for(int i=0;i<100;++i) std::cout << std::string(4096,'x') << std::flush; return 0; }
    if(scenario==L"crash") { RaiseException(0xe0005252,EXCEPTION_NONCONTINUABLE,0,nullptr); return 1; }
    throw std::runtime_error("unknown isolation fixture");
}
